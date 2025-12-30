import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

import argparse

def check_status(course_id=4, module_index=0):
    db = SessionLocal()
    try:
        course = db.query(k_models.HybridCurriculum).get(course_id)
        if not course:
            print("Course not found")
            return

        mod = course.structured_json["modules"][module_index]
        print(f"Module {module_index}: {mod['title']}")
        print(f"Total Lessons: {len(mod['lessons'])}")
        
        complete_count = 0
        for l in mod["lessons"]:
            status = l.get("status", "pending")
            print(f"- {l['title']}: {status}")
            if status == "complete":
                complete_count += 1
                
        print(f"\nCompleted Lessons: {complete_count}/{len(mod['lessons'])}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args()
    check_status(module_index=args.index)
