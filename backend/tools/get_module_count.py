import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

def get_module_count(course_id=4):
    db = SessionLocal()
    try:
        course = db.query(k_models.HybridCurriculum).get(course_id)
        if not course:
            return 0
        return len(course.structured_json["modules"])
    finally:
        db.close()

if __name__ == "__main__":
    print(get_module_count())
