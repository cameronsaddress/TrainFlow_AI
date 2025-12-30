import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

def main():
    db = SessionLocal()
    try:
        course = db.query(k_models.HybridCurriculum).get(4)
        if not course:
            return
            
        print("--- Lessons with Video Clips ---")
        count = 0
        for mod in course.structured_json.get("modules", []):
            for lesson in mod.get("lessons", []):
                clips = lesson.get("source_clips", [])
                if clips:
                    print(f"LESSON: {lesson.get('title')}")
                    for c in clips:
                        print(f"  - {c['video_filename']} ({c['start_time']}s)")
                    count += len(clips)
        print(f"Total Clips in Course: {count}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
