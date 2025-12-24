
import asyncio
import os
import sys
import json
from sqlalchemy.orm import Session

# Add parent dir to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import curriculum_architect

async def run_manual_generation():
    print("🚀 Starting Manual Curriculum Generation...", flush=True)
    db: Session = SessionLocal()
    
    try:
        # Singleton Logic: Purge previous
        print("Cleaning old records...", flush=True)
        db.query(k_models.TrainingCurriculum).delete()
        db.commit()
        
        generator = curriculum_architect.generate_curriculum(db)
        
        async for item in generator:
            if isinstance(item, str):
                print(f"STATUS: {item}", flush=True)
            elif isinstance(item, dict):
                print("✅ GENERATION COMPLETE! Saving to DB...", flush=True)
                new_plan = k_models.TrainingCurriculum(
                    title=item.get("course_title", "Untitled Course"),
                    structured_json=item
                )
                db.add(new_plan)
                db.commit()
                db.refresh(new_plan)
                print(f"🎉 SAVED! ID: {new_plan.id}, Title: {new_plan.title}")
                
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_manual_generation())
