
import sys
import os

# App is at /app/app, so adding /app to path allows 'from app.models...'
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
# CORRECTED IMPORT: HybridCurriculum is in knowledge.py
from app.models.knowledge import HybridCurriculum

# Manual DB connection
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@trainflow-db:5432/trainflow"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_course_4():
    db = SessionLocal()
    try:
        course = db.query(HybridCurriculum).filter(HybridCurriculum.id == 4).first()
        if not course:
            print("Course 4 not found")
            return

        json_data = course.structured_json
        if not json_data or 'modules' not in json_data:
            print("No structured json or modules")
            return

        print(f"Course: {course.title}")
        
        count_default = 0
        count_set = 0
        
        for mod in json_data['modules']:
            for lesson in mod.get('lessons', []):
                ref = lesson.get('pdf_reference')
                if ref:
                    page = ref.get('page_number')
                    anchor = ref.get('anchor_text')
                    
                    # Print first few to verify
                    if count_default + count_set < 5:
                         print(f"Lesson: {lesson.get('title', 'Unknown')[:30]}... | Page: {page} | Anchor: {anchor[:30] if anchor else 'None'}")

                    if str(page) == '1':
                        count_default += 1
                    else:
                        count_set += 1

        print(f"\nSummary:")
        print(f"Pages set to 1 (Default): {count_default}")
        print(f"Pages set to value > 1: {count_set}")

    finally:
        db.close()

if __name__ == "__main__":
    check_course_4()
