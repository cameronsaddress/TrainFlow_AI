from openai import AsyncOpenAI
import os
import json
import httpx
import re
from pydantic import BaseModel, ValidationError
import hashlib
from sqlalchemy.orm import Session
from ..db import SessionLocal
from ..models import knowledge as k_models

# GB10 Optimization: Point to Local NIM
# Defaults to local service in docker-compose, or falls back to public API
BASE_URL = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "dummy-key-for-local-nim")
MODEL_NAME = os.getenv("LLM_MODEL", "meta/llama3-70b-instruct")

print(f"Initializing LLM Client: {BASE_URL} with model {MODEL_NAME}")

client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    timeout=300.0
)

STEP_PROMPT = """
You are an expert technical writer. 
Analyze the following raw step data (ASR text + Visual elements) and rewrite it into a clear, atomic action step.
Format:
{
    "action": "Verb + Object (e.g. Click 'Submit')",
    "expected_result": "What should happen (e.g. Dashboard loads)",
    "notes": "Any potential warnings or tips",
    "error_potential": "Low/Medium/High",
    "field_details": [
        {"label": "Username", "required": true, "validation": "Email format"}
    ]
}
"""

DECISION_PROMPT = """
Analyze the following sequence of user actions and narration to identify the logical flow.
Output JSON format:
{
    "logic_type": "linear",  
    "explanation": "Why this logic applies",
    "decision_node_index": -1, 
    "conditions": ["Condition A", "Condition B"]
}
"""



# --- CACHE HELPERS ---
def get_input_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def get_cached_response(prompt_content: str, system_content: str, model: str) -> str:
    """Synchronous check of DB cache (Blocking, but fast)."""
    # Hash the COMBINED input to ensure uniqueness
    # We treat system_content as part of the unique key or just hash everything.
    # To be safe: Hash = sha256(model + system + prompt)
    combined = model + system_content + prompt_content
    req_hash = get_input_hash(combined)
    
    db = SessionLocal()
    try:
        entry = db.query(k_models.LLMRequestCache).filter(k_models.LLMRequestCache.request_hash == req_hash).first()
        if entry:
            # We store it as JSON object in DB, but return as string for consistency with ref API
            # Wait, the DB column is JSON. SQLAlchemy returns python dict/list.
            # We need to return string so the caller can json.loads() it (or validate it).
            return json.dumps(entry.response_json)
    except Exception as e:
        print(f"Cache Read Error: {e}")
    finally:
        db.close()
    return None

def save_cached_response(prompt_content: str, system_content: str, response_json_str: str, model: str):
    """Saves valid JSON response to DB."""
    combined = model + system_content + prompt_content
    req_hash = get_input_hash(combined)
    
    db = SessionLocal()
    try:
        # Parse string to dict for JSONB column
        try:
            data_obj = json.loads(response_json_str)
        except:
            print(f"Skipping Cache Save: Response is not valid JSON.")
            return

        # Check dupes
        existing = db.query(k_models.LLMRequestCache).filter(k_models.LLMRequestCache.request_hash == req_hash).first()
        if existing:
            return

        new_entry = k_models.LLMRequestCache(
            request_hash=req_hash,
            prompt_content=prompt_content, # We store the combined prompt here effectively? No, caller passes prompt_content.
            # Actually, let's just store the inputs.
            # wait, helper signature says prompt_content is "combined"?
            # usage above: save_cached_response(full_prompt, ...)
            # Let's align.
            system_content=system_content,
            response_json=data_obj,
            model=model
        )
        db.add(new_entry)
        db.commit()
    except Exception as e:
        print(f"Cache Write Error: {e}")
    finally:
        db.close()

def refine_step(raw_text: str, ui_context: str):
    """
    Refines a raw step using Llama 3 70B (via NIM) or GPT-4.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": STEP_PROMPT},
                {"role": "user", "content": f"Text: {raw_text}\nUI Context: {ui_context}"}
            ],
            # Llama 3 supports json_mode usually, but let's be safe
            # If NIM supports it, great. If not, text parsing might be needed.
            # Most modern NIMs support response_format={"type": "json_object"}
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"LLM Error ({MODEL_NAME}): {e}")
        # Fallback
        return {
            "action": raw_text[:50], 
            "expected_result": "Action completed", 
            "notes": raw_text,
            "error_potential": "Unknown"
        }

def detect_logic_patterns(steps_text: list):
    """
    Analyzes a list of steps to find branching logic.
    """
    prompt = "\n".join([f"{i+1}. {txt}" for i, txt in enumerate(steps_text)])
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": DECISION_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Logic Detection Error: {e}")
        return {"logic_type": "linear", "explanation": "Fallback due to error", "branches": []}

SEGMENTATION_PROMPT = """
You are a master process analyst. 
The following text is a transcription of a training video. 
Break this text down into a sequential list of clear, atomic, actionable steps.
Ignore filler words like "um", "uh", "you know".
Output JSON format:
{
    "steps": [
        "Step 1 action...",
        "Step 2 action..."
    ]
}
"""

def segment_transcript(full_text: str):
    """
    Breaks a long transcript into discrete steps using the LLM.
    """
    MAX_CHUNK_SIZE = 2000000 # ~500k tokens. (Gemini 1M context handles this easily).
    # 3 hours audio = ~30k words = ~150k chars. So this limit allows 30+ hours without chunking.
    
    if len(full_text) < MAX_CHUNK_SIZE:
        # Small enough to process in one go
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SEGMENTATION_PROMPT},
                    {"role": "user", "content": full_text}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content).get("steps", [])
        except Exception as e:
            print(f"Segmentation Error: {e}")
            return [full_text]
            
    else:
        # chunk it
        print(f"Transcript too long ({len(full_text)} chars). Chunking...")
        chunks = [full_text[i:i+MAX_CHUNK_SIZE] for i in range(0, len(full_text), MAX_CHUNK_SIZE)]
        all_steps = []
        
        for i, chunk in enumerate(chunks):
            try:
                print(f"Processing Chunk {i+1}/{len(chunks)}...")
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SEGMENTATION_PROMPT},
                        {"role": "user", "content": f"(Part {i+1}) {chunk}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                steps = json.loads(response.choices[0].message.content).get("steps", [])
                all_steps.extend(steps)
            except Exception as e:
                print(f"Chunk {i} Error: {e}")
                
        return all_steps

def repair_cutoff_json(json_str: str) -> str:
    """
    Attempts to repair a truncated JSON string by closing open braces/brackets.
    """
    json_str = json_str.strip()
    
    # 1. Simple check: if it looks complete, return it
    if json_str.endswith("}") or json_str.endswith("]"):
        return json_str
        
    # 2. Stack-based repair
    stack = []
    is_in_string = False
    escape = False
    
    # If cut off inside a string, close the string first
    # We need to scan to track state
    for char in json_str:
        if escape:
            escape = False
            continue
            
        if char == '\\':
            escape = True
            continue
            
        if char == '"':
            is_in_string = not is_in_string
            continue
            
        if not is_in_string:
            if char == '{':
                stack.append('}')
            elif char == '[':
                stack.append(']')
            elif char == '}' or char == ']':
                if stack:
                    stack.pop()
                    
    # If ended inside string, close it
    if is_in_string:
        json_str += '"'
        
    # Pop remaining stack to close structure
    while stack:
        closer = stack.pop()
        json_str += closer
        
    return json_str

async def generate_text(prompt: str, model: str = None, max_tokens: int = 128000) -> str:
    """
    Generic text generation utility for Knowledge Engine (Async).
    Allows overriding the default model.
    """
    target_model = model if model else MODEL_NAME
    try:
        response = await client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM Generation Error: {e}")
        return ""

async def get_embedding(text: str) -> list:
    """
    Generates vector embedding for text using OpenAI/compatible API (Async).
    Returns list of floats.
    """
    try:
        response = await client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding Error: {e}")
        return []

SYNTHESIS_PROMPT = """
You are a "Hyper-Learning" Instructor.
Your goal is to convert a raw video step into a concise, rule-compliant training action.

Input:
1. Raw Step: "User kinda clicks the save button I guess"
2. Relevant Rules: 
   - "Must verify ZIP code before Save."
   - "Do not click Save if status is Offline."

Output JSON:
{
    "refined_action": "Verify ZIP Code, then click Save.",
    "compliance_warnings": ["Do not click if status is Offline"],
    "criticality": "HIGH"
}
"""

async def refine_instruction_with_rules(raw_text: str, rules: list) -> dict:
    """
    Synthesizes a clean instruction merged with compliance rules (Async).
    """
    rules_text = "\n".join([f"- {r}" for r in rules])
    user_content = f"Raw Step: \"{raw_text}\"\nRelevant Rules:\n{rules_text}"
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Rule Synthesis Error: {e}")
        return {
            "refined_action": raw_text,
            "compliance_warnings": [],
            "criticality": "LOW"
        }

async def generate_structure(system_prompt: str, user_content: str, model: str = None, max_tokens: int = 128000) -> dict:
    """
    Generic structured generation using JSON mode (Async).
    """
    target_model = model if model else MODEL_NAME
    
    # 1. Cache Check
    full_prompt = system_prompt + user_content
    response_format_str = "json_object"
    cached_json_str = get_cached_response(full_prompt, response_format_str, target_model)
    if cached_json_str:
        print("[CACHE HIT] generate_structure returning stored JSON.")
        return json.loads(cached_json_str)

    try:
        response = await client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=max_tokens
        )
        content = response.choices[0].message.content
        fixed_content = repair_cutoff_json(content)
        
        # Cache Save
        save_cached_response(full_prompt, response_format_str, fixed_content, target_model)
        
        return json.loads(fixed_content)
    except Exception as e:
        print(f"Structure Generation Error: {e}")
        return {"error": str(e), "status": "failed"}

async def generate_structure_validated(
    system_prompt: str, 
    user_content: str, 
    model_class: type[BaseModel], 
    model: str = None,
    max_retries: int = 2
) -> BaseModel:
    """
    Robust generation with Pydantic Validation & Reflection Retry (Async).
    """
    target_model = model if model else MODEL_NAME
    
    # 1. Cache Check
    full_prompt = system_prompt + user_content
    # Simple hash of inputs
    cached_json_str = get_cached_response(full_prompt, "json_object", target_model)
    if cached_json_str:
        try:
            print("[CACHE HIT] generate_structure_validated returning stored JSON.")
            return model_class.model_validate_json(cached_json_str)
        except Exception as e:
            print(f"[CACHE CORRUPT] Cached JSON failed info validation: {e}. Re-generating.")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=target_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=128000
            )
            raw_json = response.choices[0].message.content
            
            # Basic repair
            raw_json = repair_cutoff_json(raw_json)
            
            # Validate FIRST
            validated_obj = model_class.model_validate_json(raw_json)

            # Cache Save (Only if Valid)
            save_cached_response(full_prompt, "json_object", raw_json, target_model)

            return validated_obj
            
        except ValidationError as e:
            print(f"Validation Error (Attempt {attempt+1}): {e}")
            
            # DEBUG: Dump failed JSON to file
            try:
                with open("llm_failure_dump.txt", "w") as f:
                    f.write(raw_json)
                print("DUMPED FAILED JSON TO llm_failure_dump.txt")
            except:
                pass

            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw_json})
                messages.append({
                    "role": "user", 
                    "content": f"JSON Validation Failed. \nErrors: {e}\n\nPlease regenerate the JSON correcting exactly these errors."
                })
            else:
                raise e
        except Exception as e:
            print(f"Gen Error (Attempt {attempt+1}): {e}")
            if attempt == max_retries:
                raise e
                
    raise Exception("Max retries exceeded")
