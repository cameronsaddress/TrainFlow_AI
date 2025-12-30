import sys
import json
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
        mod_0 = j['modules'][0]
        
        print(f"Module 0 Title: {mod_0.get('title')}")
        print(f"Lesson Count: {len(mod_0.get('lessons', []))}")
        
        for idx, l in enumerate(mod_0.get('lessons', [])):
            print(f"[{idx}] {l.get('title')}")
            print(f"     Audio: {l.get('instructor_audio')}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
