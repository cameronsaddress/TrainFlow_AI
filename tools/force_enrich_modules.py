import asyncio
import logging
import sys
import os

# Ensure backend modules are visible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import curriculum_architect, llm

# Explicitly bypass cache by appending this to context
SALT = "<!-- FORCE_REGEN: 2025-12-27_MANUAL_FIX -->"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def surgical_regenerate():
    db = SessionLocal()
    try:
        # Load Course 14
        course = db.query(k_models.TrainingCurriculum).get(14)
        if not course:
            logger.error("Course 14 not found!")
            return

        master_plan = course.structured_json
        modules = master_plan.get("modules", [])
        
        logger.info(f"--- Analyzing Course 14 ({len(modules)} Modules) ---")
        
        updated_any = False
        
        for i, mod in enumerate(modules):
            lessons = mod.get("lessons", [])
            title = mod.get("title")
            
            if len(lessons) > 0:
                logger.info(f"✅ Module {i+1}: {len(lessons)} Lessons (Skipping)")
                continue
                
            logger.info(f"⚠️ Module {i+1}: EMPTY. Regenerating...")
            
            # 1. Rebuild Context
            source_filenames = mod.get("recommended_source_videos", [])
            video_objs = []
            if source_filenames:
                video_objs = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename.in_(source_filenames)).all()
            
            if not video_objs:
                 logger.warning(f"   No source videos found for '{title}'. Skipping.")
                 continue
                 
            context_str = curriculum_architect.build_full_context(video_objs)
            # SALT THE CONTEXT TO MISS CACHE
            context_str += f"\n{SALT}"
            
            # 2. Generate
            try:
                # We reuse the logic from `generate_detailed_module_validated`
                # But we call it directly here
                new_module = await curriculum_architect.generate_detailed_module_validated(mod, context_str)
                
                # 3. Enrich (Parallel)
                logger.info("   Enriching (Smart Assist)...")
                new_lessons = new_module.get("lessons", [])
                
                semaphore = asyncio.Semaphore(5)
                tasks = []
                for lesson in new_lessons:
                    tasks.append(curriculum_architect.enrich_lesson_worker(
                        lesson, 
                        "Senior Utility Trainer", 
                        "Work Order Clerk", 
                        "Utility Operations", 
                        "Procedures, Safety, Data Integrity", 
                        semaphore
                    ))
                
                enriched_lessons = await asyncio.gather(*tasks)
                new_module["lessons"] = enriched_lessons
                
                # 4. Save to DB IMMEDIATELY
                modules[i] = new_module
                course.structured_json = master_plan
                # Force update
                # SQLAlchemy JSON types sometimes need explicit flag modified
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(course, "structured_json")
                
                db.commit()
                logger.info(f"   💾 SAVED Module {i+1} ({len(enriched_lessons)} Lessons)")
                updated_any = True
                
            except Exception as e:
                logger.error(f"   ❌ Failed to regenerate Module {i+1}: {e}")

        if updated_any:
            logger.info("--- Surgical Regeneration Complete: DB Updated ---")
        else:
            logger.info("--- No Empty Modules Found / No Changes ---")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(surgical_regenerate())
