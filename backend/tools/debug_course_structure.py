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
        if not j:
            print("structured_json is None or Empty")
            return
            
        print(f"Top Level Keys: {list(j.keys())}")
        
        modules = j.get('modules')
        if modules is None:
            print("'modules' key is missing or None")
        elif isinstance(modules, list):
            print(f"Module Count: {len(modules)}")
            for idx, m in enumerate(modules):
                title = m.get('title', 'NO_TITLE')
                l_count = len(m.get('lessons', []))
                print(f"  [{idx}] {title} ({l_count} lessons)")
        else:
            print(f"'modules' is type {type(modules)}, expected list")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
