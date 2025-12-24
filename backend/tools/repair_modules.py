
import asyncio
import os
import sys
import json
from sqlalchemy.orm import Session

# Add parent dir to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.schemas.curriculum import Module, Lesson
from openai import AsyncOpenAI
from pydantic import ValidationError

# Configuration
API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("LLM_API_BASE", "https://openrouter.ai/api/v1")
MODEL_NAME = os.getenv("LLM_MODEL", "x-ai/grok-4.1-fast")

client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    timeout=200.0 # Increased timeout for repairs
)

# Utility to clean JSON
def repair_cutoff_json(json_str: str) -> str:
    json_str = json_str.strip()
    # If it seems cut off...
    if not json_str.endswith("}") and not json_str.endswith("]"):
        # Remove trailing commas
        json_str = json_str.rstrip(", \n\t")
        # Count braces
        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        open_brackets = json_str.count("[")
        close_brackets = json_str.count("]")
        
        # Add missing closures
        json_str += "]" * (open_brackets - close_brackets)
        json_str += "}" * (open_braces - close_braces)
        
    return json_str

async def generate_structure_validated(
    system_prompt: str, 
    user_content: str, 
    model_class: type[BaseModel], 
    use_simple_prompt: bool = False,
    max_retries: int = 3
) -> BaseModel:
    """
    Robust generation with Pydantic Validation & Reflection Retry.
    Supports 'use_simple_prompt' flag to reduce output verbosity if needed.
    """
    
    # If simple prompt requested (fallback mode), append guidance
    if use_simple_prompt:
        system_prompt += " \nIMPORTANT: KEEP RESPONSE CONCISE. Avoid excessively long scripts."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    for attempt in range(max_retries + 1):
        try:
            print(f"  Attempt {attempt + 1} (Simple={use_simple_prompt})...", flush=True)
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=128000
            )
            raw_json = response.choices[0].message.content
            
            # Basic repair if needed
            if not raw_json.strip().endswith("}"):
                 raw_json = repair_cutoff_json(raw_json)
            
            # Validate
            validated_obj = model_class.model_validate_json(raw_json)
            return validated_obj
            
        except ValidationError as e:
            print(f"  Validation Error: {e}")
            messages.append({"role": "assistant", "content": raw_json})
            messages.append({
                "role": "user", 
                "content": f"JSON Validation Failed. \nErrors: {e}\n\nPlease regenerate the JSON correcting these specific errors."
            })
        except Exception as e:
            print(f"  Gen Error: {e}")
            # Non-validation error, maybe transient?
            if attempt == max_retries:
                raise e
                
    raise Exception("Max retries exceeded")

async def repair_curriculum():
    db: Session = SessionLocal()
    try:
        # Get Latest
        curriculum = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        if not curriculum:
            print("No curriculum found.")
            return

        print(f"Inspecting Curriculum: {curriculum.title}")
        data = curriculum.structured_json
        modules = data.get("modules", [])
        
        updates_made = False
        
        # Build Summary Context for Fallback
        all_videos = db.query(k_models.VideoCorpus).all()
        summaries = []
        for v in all_videos:
             meta = v.metadata_json or {}
             s = meta.get("summary", "")
             if s:
                 summaries.append(f"<VIDEO_SUMMARY filename='{v.filename}'>\n{s}\n</VIDEO_SUMMARY>")
        full_summary_context = "\n".join(summaries)
        
        for i, module in enumerate(modules):
            # Detect Failure
            is_failed = False
            if "error" in module:
                is_failed = True
            elif "lessons" not in module:
                is_failed = True
            elif not module.get("lessons"):
                is_failed = True
                
            if is_failed:
                print(f"Reparing Module {i+1}: {module.get('title')}...")
                
                # Re-construct context
                source_filenames = module.get("recommended_source_videos", [])
                module_videos = [v for v in all_videos if v.filename in source_filenames]
                
                # FALLBACK STRATEGY: 
                # If specifically Module 10 (or failed due to size), try using SUMMARIES first?
                # Or just try full context but with "Simple Prompt" flag.
                
                context_str = ""
                use_summary_fallback = False
                
                # Heuristic: If we failed before, maybe context is too big or output too verbose.
                
                if not module_videos:
                    context_str = full_summary_context
                    use_summary_fallback = False # Already using summary
                else:
                    # Construct full context
                    for v in module_videos:
                         # Hacky reconstruct XML
                         context_str += f"<VIDEO filename='{v.filename}'>\n"
                         context_str += (v.transcript_text or "")
                         context_str += "\n</VIDEO>"
                    
                    # If this context is massive (>1M chars), maybe fallback to summary? (Module 10 context is huge?)
                    # Let's try full context first, but if it fails inside generate_structure, catch and retry with summary?
                    
                # Generate
                prompt = f"""
                You are the Content Developer.
                We are detailing the Module: "{module.get('title')}".
                
                Context:
                {context_str[:2000000]} 
                
                Task: Create detailed Lessons.
                Include 'source_clips' with timestamps.
                """
                
                try:
                    # Try Attempt A: Full Context (Standard)
                    new_module: Module = await generate_structure_validated(
                        system_prompt="You are a meticulous content developer.",
                        user_content=prompt,
                        model_class=Module,
                        max_retries=2
                    )
                    modules[i] = new_module.model_dump()
                    updates_made = True
                    print(f"  ✅ Repaired Module {i+1} (Standard)")
                    
                except Exception as e:
                    print(f"  ⚠️ Standard Repair Failed: {e}")
                    print("  🔄 Switching to FALLBACK (Summary Context)...")
                    
                    # Try Attempt B: Summary Context (Lighter)
                    fallback_prompt = f"""
                    You are the Content Developer.
                    We are detailing the Module: "{module.get('title')}".
                    
                    Context (Summarized):
                    {full_summary_context}
                    
                    Task: Create detailed Lessons.
                    """
                    
                    try:
                         new_module: Module = await generate_structure_validated(
                            system_prompt="You are a meticulous content developer.",
                            user_content=fallback_prompt,
                            model_class=Module,
                            use_simple_prompt=True
                        )
                         modules[i] = new_module.model_dump()
                         updates_made = True
                         print(f"  ✅ Repaired Module {i+1} (Fallback)")
                    except Exception as e2:
                        print(f"  ❌ Failed to repair Module {i+1} even with Fallback: {e2}")

        if updates_made:
            data["modules"] = modules
            curriculum.structured_json = data
            db.commit()
            print("Database updated with repaired modules.")
        else:
            print("No repairs needed or all failed.")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(repair_curriculum())
