import sys
import os

# Add backend to path
sys.path.append('/home/canderson/TrainFlow_AI/backend')

from app.db import SessionLocal
from app.models.knowledge import TrainingCurriculum

def audit_course(course_id):
    db = SessionLocal()
    course = db.query(TrainingCurriculum).get(course_id)
    if not course:
        print(f"Course {course_id} not found.")
        return

    print(f"AUDIT REPORT: {course.title}")
    data = course.structured_json
    
    for mod in data.get("modules", []):
        title = mod.get("title")
        lessons = mod.get("lessons", [])
        
        total_clips = 0
        total_script_chars = 0
        
        for l in lessons:
            clips = l.get("source_clips", [])
            total_clips += len(clips)
            script = l.get("voiceover_script", "")
            total_script_chars += len(script)
            
        print(f"\nModule: {title}")
        print(f"  - Lesson Count: {len(lessons)}")
        print(f"  - Total Video Clips Cited: {total_clips}")
        print(f"  - Total Script content: {total_script_chars} characters")
        print(f"  - Density: {total_clips / len(lessons) if lessons else 0:.1f} clips per lesson")

if __name__ == "__main__":
    audit_course(22)
