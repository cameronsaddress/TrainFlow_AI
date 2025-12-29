import sys
import os

# Add backend to path (Support Local and Docker)
sys.path.append('/home/canderson/TrainFlow_AI/backend')
sys.path.append('/app')

from app.db import SessionLocal
from app.models.knowledge import TrainingCurriculum

def audit_course(course_id):
    db = SessionLocal()
    try:
        course = db.query(TrainingCurriculum).get(course_id)
        if not course:
            print(f"❌ Course {course_id} NOT FOUND in DB.")
            return

        print(f"✅ Course {course_id} Found: '{course.title}'")
        data = course.structured_json
        modules = data.get("modules", [])
        print(f"📦 Modules: {len(modules)}")

        total_lessons = 0
        total_scripts = 0
        
        for m in modules:
            lessons = m.get("lessons", [])
            print(f"  - Module '{m.get('title')}': {len(lessons)} lessons")
            total_lessons += len(lessons)
            
            for l in lessons:
                script = l.get("voiceover_script", "")
                if len(script) < 10:
                    print(f"    ⚠️ Lesson '{l.get('title')}' has suspicious script length: {len(script)}")
                else:
                    total_scripts += 1
                
                clips = l.get("source_clips", [])
                if not clips:
                     print(f"    ⚠️ Lesson '{l.get('title')}' has NO source clips.")

        print(f"📊 Total Lessons: {total_lessons}")
        print(f"🎙️ Valid Scripts: {total_scripts}/{total_lessons}")
        
        if total_lessons > 0 and total_scripts == total_lessons:
             print("🌟 AUDIT PASSED: Content is Complete.")
        else:
             print("⚠️ AUDIT WARNING: Potential missing content.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    audit_course(27)
