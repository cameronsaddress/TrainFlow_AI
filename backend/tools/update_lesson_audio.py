import sys
from sqlalchemy import text
sys.path.append('/app')
from app.db import SessionLocal
from app.models.knowledge import HybridCurriculum

def main():
    db = SessionLocal()
    try:
        # Get Course 4
        course = db.query(HybridCurriculum).filter(HybridCurriculum.id == 4).first()
        if not course:
            print("Course 4 not found")
            return
            
        j = course.structured_json
        updated = False
        
        # Search for "Pole Specification" or similar
        # User said: "Section 2, Pole Specifications and Identification"
        
        for m_idx, m in enumerate(j.get("modules", [])):
            for l_idx, l in enumerate(m.get("lessons", [])):
                title = l.get("title", "").lower()
                if "pole spec" in title or "pole identification" in title or "specification and identification" in title:
                    print(f"MATCH FOUND: Module {m_idx}, Lesson {l_idx}: {l.get('title')}")
                    
                    # Update the field
                    l["instructor_audio"] = "/audio/lessons/lesson_2_instructor.mp3"
                    updated = True
                    # Don't break immediately, in case there are duplicates, but usually first match is good.
                    # actually let's break to be safe we don't hit wrong ones.
                    break
            if updated:
                break
                
        if updated:
            course.structured_json = j
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(course, "structured_json")
            db.commit()
            print("SUCCESS: Database updated with audio path.")
        else:
            print("ERROR: Target lesson not found.")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
