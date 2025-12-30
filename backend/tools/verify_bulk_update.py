import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

def main():
    db = SessionLocal()
    try:
        course = db.query(k_models.HybridCurriculum).get(4)
        struct = course.structured_json
        
        target_mod = None
        for mod in struct["modules"]:
            if "Section 1" in mod["title"] and "General" in mod["title"]:
                target_mod = mod
                break
        
        if not target_mod:
            print("Target module not found.")
            return

        print(f"Checking Module: {target_mod['title']}")
        print("-" * 60)
        
        complete_count = 0
        total_count = len(target_mod["lessons"])
        
        for lesson in target_mod["lessons"]:
            status = lesson.get("status", "pending")
            has_content = len(lesson.get("content_blocks", [])) > 0
            objective = lesson.get("learning_objective", "N/A")[:50] + "..."
            
            print(f"Lesson: {lesson['title']}")
            print(f"  Status: {status}")
            print(f"  Blocks: {len(lesson.get('content_blocks', []))}")
            print(f"  Obj: {objective}")
            print(f"  PDF Ref: {lesson.get('pdf_reference')}")
            print("-" * 30)
            
            if status == "complete" and has_content:
                complete_count += 1
        
        print(f"Summary: {complete_count}/{total_count} lessons complete.")

    finally:
        db.close()

if __name__ == "__main__":
    main()
