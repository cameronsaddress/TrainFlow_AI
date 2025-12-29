import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models
import json

def audit():
    db = SessionLocal()
    try:
        # 1. Fetch Course 4
        course = db.query(k_models.HybridCurriculum).get(4)
        if not course:
            print("Course 4 NOT FOUND.")
            return

        print(f"=== COURSE 4: {course.title} ===")
        print(f"Description: {course.description}")
        struct = course.structured_json
        modules = struct.get("modules", [])
        print(f"Total Modules: {len(modules)}")
        
        # 2. Fetch Document 10 (Source)
        # Note: In pipeline we hardcoded doc_id=10.
        doc = db.query(k_models.KnowledgeDocument).get(10)
        if not doc:
            print("Source Document 10 NOT FOUND.")
            return

        text = doc.extracted_text or ""
        print(f"\n=== SOURCE DOCUMENT: {doc.filename} ===")
        print(f"Total Text Length: {len(text)} characters")
        
        # 3. Analyze Coverage
        # Print Blueprint Modules
        print("\n--- BLUEPRINT MODULES ---")
        for i, m in enumerate(modules):
            print(f"{i+1}. {m['title']}")
            
        # Print Text Head (Table of Contents usually here)
        print("\n--- SOURCE TEXT HEAD (First 3000 chars) ---")
        print(text[:3000])
        
        print("\n--- SOURCE TEXT TAIL (Last 1000 chars) ---")
        print(text[-1000:])

    finally:
        db.close()

if __name__ == "__main__":
    audit()
