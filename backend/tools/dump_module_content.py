import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models

def dump_content():
    db = SessionLocal()
    try:
        curriculum = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        if not curriculum:
            print("No curriculum found.")
            return

        modules = curriculum.structured_json.get("modules", [])
        
        # Target Module 1
        if not modules:
            print("No modules found.")
            return

        m = modules[0]
        print(f"=== {m.get('title')} ===")
        
        lessons = m.get("lessons", [])
        for i, l in enumerate(lessons[:3]): # Take first 3
            print(f"\n--- Lesson {i+1}: {l.get('title')} ---")
            print(l.get("voiceover_script", "NO SCRIPT FOUND"))
            print("-" * 20)

    finally:
        db.close()

if __name__ == "__main__":
    dump_content()
