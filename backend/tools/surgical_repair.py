import sys
import os
import asyncio
import json

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import curriculum_architect, llm, video_clip
from app.schemas.curriculum import Module

async def surgical_repair():
    print("🏥 Starting Surgical Repair of Curriculum...", flush=True)
    db = SessionLocal()
    
    try:
        # 1. Fetch latest curriculum
        curriculum = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        
        if not curriculum:
            print("❌ No curriculum found to repair.", flush=True)
            return

        print(f"✅ Found Curriculum: {curriculum.title} (ID: {curriculum.id})", flush=True)
        data = curriculum.structured_json
        modules = data.get("modules", [])
        
        # Pre-fetch all summaries for fallback
        print("  📥 Pre-fetching global context (all summaries)...")
        all_videos = db.query(k_models.VideoCorpus).all()
        global_summaries = []
        for v in all_videos:
            if v.metadata_json.get("summary"):
                global_summaries.append(f"Video: {v.filename}\nSummary: {v.metadata_json.get('summary')}")
        global_context_str = "\n\n".join(global_summaries)
        
        repair_count = 0
        
        # 2. Scan and Fix
        for i in range(len(modules)):
            # Re-read module from current data state (in case of partial saves? no, data var is local)
            module = modules[i]
            
            title = module.get("title", f"Module {i+1}")
            lessons = module.get("lessons", [])
            error = module.get("error")
            
            needs_repair = False
            
            # Heuristic: Repair if marked error OR invalid lesson count (< 3 is suspicious for a full module)
            if error:
                 print(f"⚠️ Module {i+1} '{title}' has error: {error}. Marking for repair.", flush=True)
                 needs_repair = True
            elif not lessons or len(lessons) < 3:
                 print(f"⚠️ Module {i+1} '{title}' has {len(lessons)} lessons. Suspiciously low/empty. Marking for repair.", flush=True)
                 needs_repair = True
                 
            # Fix empty titles if possible
            if needs_repair and (not title or title.strip() == "" or title == "Module"):
                 print(f"  ⚠️ Title is missing. Assigning generic title 'Module {i+1}'.")
                 title = f"Module {i+1}"
                 module["title"] = title

            if needs_repair:
                print(f"🚑 REPAIRING Module {i+1} '{title}'...", flush=True)
                
                # Context Build
                source_filenames = module.get("recommended_source_videos", [])
                
                from app.services.curriculum_architect import build_full_context
                
                videos = []
                for fname in source_filenames:
                    v = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename == fname).first()
                    if v:
                        videos.append(v)
                
                context = ""
                if videos:
                    print(f"  Using {len(videos)} specific source videos.")
                    context = build_full_context(videos)
                
                # Fallback to global context if specific context is empty
                if not context.strip():
                     print("  ⚠️ No specific videos found. Using GLOBAL SUMMARY context (16 videos).")
                     context = global_context_str

                if not context.strip():
                     print("  ❌ No context available at all. Skipping repair.")
                     continue

                # RE-GENERATE using CHUNKING explicitly
                # We call generate_module_in_chunks directly to force fidelity
                try:
                    repaired_module = await curriculum_architect.generate_module_in_chunks(module, context)
                    
                    # ENRICH (Mini-Enrichment) - SKIPPING FOR SPEED
                    # enriched_lessons = []
                    # for lesson in repaired_module.get("lessons", []):
                    #     script = lesson.get("voiceover_script", "")
                    #     if script:
                    #         context_prompt = f"Analyze this Training Script and generate 'Smart Assist' metadata.\nScript: {script}"
                    #         try:
                    #             smart_context = await llm.generate_structure(
                    #                 system_prompt="You are a Compliance & Support AI. Extract actionable guardrails.",
                    #                 user_content=context_prompt,
                    #                 model="x-ai/grok-4.1-fast"
                    #             )
                    #             lesson["smart_context"] = smart_context
                    #         except:
                    #             lesson["smart_context"] = {}
                    #     enriched_lessons.append(lesson)
                    
                    # repaired_module["lessons"] = enriched_lessons
                    pass
                    
                    # Remove error flag
                    if "error" in repaired_module:
                        del repaired_module["error"]
                        
                    # IMMEDIATE SAVE
                    modules[i] = repaired_module
                    data["modules"] = modules
                    curriculum.structured_json = data
                    
                    # Using flag_modified if using JSON mutation tracking (SQLAlchemy sometimes passes by ref)
                    # For safety, force update
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(curriculum, "structured_json")
                    
                    db.commit()
                    db.refresh(curriculum)
                    
                    repair_count += 1
                    print(f"  ✅ Module {i+1} Repaired & SAVED Successfully.", flush=True)
                    
                except Exception as e:
                    print(f"  ❌ Repair Failed for Module {i+1}: {e}", flush=True)
                    # Keep broken one, don't save
            else:
                 # No repair needed
                 pass
        
        print(f"✨ Repair Cycle Complete. Total Fixed: {repair_count}", flush=True)
            
    except Exception as e:
        print(f"💥 Surgical Repair Crashed: {e}", flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(surgical_repair())
