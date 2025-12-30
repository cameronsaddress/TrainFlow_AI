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
        
        # Hardcoded Restore Point (from Step 942 logs)
        new_lessons = [
            {"title": "Foreword and Purpose of National Grid Distribution Standards", "instructor_audio": ""},
            {"title": "Copyright Notice and Standards Ownership", "instructor_audio": ""},
            {"title": "Basic Insulation Level (BIL) Ratings", "instructor_audio": ""},
            {"title": "Transmission and Sub-Transmission Voltages", "instructor_audio": ""},
            {"title": "Primary Distribution Voltages", "instructor_audio": ""},
            {"title": "Secondary Distribution Voltages", "instructor_audio": ""},
            {"title": "General Rules and Compliance Guidelines", "instructor_audio": ""},
            {"title": "Checklists and Document Control", "instructor_audio": ""},
            {"title": "Abbreviations", "instructor_audio": ""},
            {"title": "Definitions", "instructor_audio": ""}
        ]
        
        # Preserve other props of existing lessons if possible? 
        # The previous 'enrichment' might have added 'content_blocks'. 
        # Those are likely junk now if the titles changed.
        # We will reset to clean state.
        
        j['modules'][0]['title'] = "Section 1 – General"
        j['modules'][0]['lessons'] = new_lessons
        
        course.structured_json = j
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(course, "structured_json")
        db.commit()
        print("SUCCESS: Module 0 restored to 10 lessons.")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
