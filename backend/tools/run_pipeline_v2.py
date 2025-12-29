
import asyncio
import sys
sys.path.append("/app")

from app.db import SessionLocal
from app.services import hybrid_pipeline_v2
from app.models import knowledge as k_models

async def main():
    db = SessionLocal()
    try:
        # 1. Trigger Stage 1 (Resume Mode)
        print("--- STARTING STAGE 1: GROK GENERATION (RESUME) ---")
        # Doc ID 10 is the OH Complete Book 2025
        # This will detect existing Course 4 and resume drafting lessons.
        course = await hybrid_pipeline_v2.stage_1_generate_course(db, doc_id=10)
        print(f"Stage 1 Complete. Course ID: {course.id}")
        
        # 2. Trigger Stage 2
        print("--- STARTING STAGE 2: VIDEO FUSION ---")
        await hybrid_pipeline_v2.stage_2_enrich_with_video(db, course.id)
        print("--- PIPELINE COMPLETE ---")
        
    except Exception as e:
        print(f"Pipeline Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
