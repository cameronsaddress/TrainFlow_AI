import sys
import os
import json

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models
from sqlalchemy.orm.attributes import flag_modified

def patch_curriculum():
    print("🩹 Starting Schema Patch for Curriculum 11...", flush=True)
    db = SessionLocal()
    try:
        curriculum = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        if not curriculum:
            print("❌ No curriculum found.")
            return

        data = curriculum.structured_json
        modules = data.get("modules", [])
        
        fixed_count = 0
        
        for m in modules:
            for l in m.get("lessons", []):
                # 1. Fix Source Clips Schema
                if "source_clips" in l and isinstance(l["source_clips"], list):
                    for clip in l["source_clips"]:
                        # Migrate filename -> video_filename
                        if "filename" in clip and "video_filename" not in clip:
                            clip["video_filename"] = clip.pop("filename")
                            fixed_count += 1
                        
                        # Migrate start -> start_time
                        if "start" in clip and "start_time" not in clip:
                            clip["start_time"] = clip.pop("start")
                        
                        # Migrate end -> end_time
                        if "end" in clip and "end_time" not in clip:
                            clip["end_time"] = clip.pop("end")
                            
                        # Ensure 'reason' exists (Frontend might not break, but good for validity)
                        if "reason" not in clip:
                            clip["reason"] = "Primary demonstration of concept."
                            
                # 2. Fix Missing Learning Objective
                if "learning_objective" not in l or not l["learning_objective"]:
                    title = l.get("title", "this lesson").replace("Lesson ", "")
                    # Heuristic derivation
                    l["learning_objective"] = f"Upon completion, the learner will understand the fundamental concepts of {title}."
                    fixed_count += 1
                    print(f"   ➕ Added objective for: {title}")

        if fixed_count > 0:
            curriculum.structured_json = data
            flag_modified(curriculum, "structured_json")
            db.commit()
            print(f"✅ Patch Applied. Fixed {fixed_count} schema issues.")
        else:
            print("✨ content is already schema-compliant.")

    finally:
        db.close()

if __name__ == "__main__":
    patch_curriculum()
