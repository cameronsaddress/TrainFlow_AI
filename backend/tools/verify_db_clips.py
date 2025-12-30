import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models
import json

def main():
    db = SessionLocal()
    try:
        course = db.query(k_models.HybridCurriculum).get(4)
        if not course:
            print("Course 4 not found")
            return
            
        target_lesson = "Lesson 2: Poles in Joint Use" # Known to have clips
        found = False
        
        for mod in course.structured_json.get("modules", []):
            for lesson in mod.get("lessons", []):
                if lesson.get("title") == target_lesson:
                    found = True
                    print(f"Data for '{target_lesson}':")
                    clips = lesson.get("source_clips", [])
                    print(json.dumps(clips, indent=2))
                    
                    # Verify fields existence
                    for i, clip in enumerate(clips):
                        missing = []
                        if "start_time" not in clip: missing.append("start_time")
                        if "end_time" not in clip: missing.append("end_time")
                        if "video_filename" not in clip: missing.append("video_filename")
                        
                        if missing:
                            print(f"ERROR: Clip {i} missing fields: {missing}")
                        else:
                            print(f"Clip {i}: OK (Start: {clip['start_time']}, End: {clip['end_time']})")

        if not found:
            print(f"Lesson '{target_lesson}' not found.")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
