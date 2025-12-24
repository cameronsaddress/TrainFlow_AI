import sys
import os
import json

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models
from sqlalchemy.orm.attributes import flag_modified

def propagate_filenames():
    print("🔧 Propagating missing video filenames...", flush=True)
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
            # Get module-level recommendation
            # e.g. "Work Order Training - Day 1 Part2.mp4"
            rec_videos = m.get("recommended_source_videos", [])
            primary_video = rec_videos[0] if rec_videos else None
            
            for l in m.get("lessons", []):
                clips = l.get("source_clips", [])
                lesson_modified = False
                
                for clip in clips:
                    # Issue: Missing 'video_filename'
                    if not clip.get("video_filename") and primary_video:
                        clip["video_filename"] = primary_video
                        lesson_modified = True
                        
                if lesson_modified:
                    fixed_count += 1
                    print(f"   ✅ Fixed Lesson: {l.get('title')} -> {primary_video}")

        if fixed_count > 0:
            curriculum.structured_json = data
            flag_modified(curriculum, "structured_json")
            db.commit()
            print(f"✅ Propagated filenames to {fixed_count} lessons.")
        else:
            print("✨ No missing filenames found.")

    finally:
        db.close()

if __name__ == "__main__":
    propagate_filenames()
