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
        m0 = j['modules'][0]
        m1 = j['modules'][1]
        
        print(f"--- Module 0: {m0.get('title')} ---")
        for l in m0.get('lessons', []):
            print(f"  {l.get('title')} [Audio: {l.get('instructor_audio')}]")
            
        print(f"\n--- Module 1: {m1.get('title')} ---")
        for l in m1.get('lessons', []):
            print(f"  {l.get('title')} [Audio: {l.get('instructor_audio')}]")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
