import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

def main():
    db = SessionLocal()
    try:
        course = db.query(k_models.HybridCurriculum).get(4)
        if not course:
            print("Course 4 not found")
            return
            
        target_lesson = "Transmission and Sub-Transmission Voltages"
        found = False
        
        for mod in course.structured_json.get("modules", []):
            for lesson in mod.get("lessons", []):
                if lesson.get("title") == target_lesson:
                    found = True
                    print(f"LESSON: {target_lesson}")
                    clips = lesson.get("source_clips", [])
                    print(f"Video Clips Found: {len(clips)}")
                    for clip in clips:
                        print(f" - {clip['video_filename']} ({clip['start_time']}s - {clip['end_time']}s)")
                        print(f"   Reason: {clip.get('reason')}")
        
        if not found:
            print(f"Lesson '{target_lesson}' not found in curriculum.")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
