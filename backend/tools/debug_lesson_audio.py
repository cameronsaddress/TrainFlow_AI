import sys
from sqlalchemy import text
sys.path.append('/app')
from app.db import SessionLocal
from app.models.knowledge import HybridCurriculum

def main():
    db = SessionLocal()
    try:
        course = db.query(HybridCurriculum).filter(HybridCurriculum.id == 4).first()
        if not course:
            print("Course 4 not found")
            return
            
        j = course.structured_json
        
        print(f"--- Course: {course.title} ---")
        for m_idx, m in enumerate(j.get("modules", [])):
            print(f"\nModule {m_idx}: {m.get('title')}")
            for l_idx, l in enumerate(m.get("lessons", [])):
                has_audio = "YES" if l.get("instructor_audio") else "NO"
                print(f"  Lesson {l_idx}: {l.get('title')} [Audio: {has_audio}]")
                if has_audio == "YES":
                    print(f"    -> Path: {l.get('instructor_audio')}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
