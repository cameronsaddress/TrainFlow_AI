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
        
        # Verify they are duplicates
        if m0['title'] != m1['title']:
            print(f"Titles differ: {m0['title']} vs {m1['title']}. Aborting auto-fix.")
            return

        print("Merging Audio from Module 0 -> Module 1...")
        
        # Map audio by lesson title
        audio_map = {}
        for l in m0.get('lessons', []):
            if l.get('instructor_audio'):
                audio_map[l['title']] = l['instructor_audio']
                
        # Apply to Module 1
        updated_count = 0
        for l in m1.get('lessons', []):
            if l['title'] in audio_map:
                l['instructor_audio'] = audio_map[l['title']]
                updated_count += 1
                
        print(f"Updated {updated_count} lessons in Module 1.")
        
        # Remove Module 0
        print("Removing duplicate Module 0...")
        j['modules'].pop(0)
        
        course.structured_json = j
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(course, "structured_json")
        db.commit()
        print("SUCCESS: Duplicates merged and resolved.")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
