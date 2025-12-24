import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models

def debug_lesson_content():
    db = SessionLocal()
    try:
        curriculum = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        if not curriculum:
            print("No curriculum found.")
            return

        modules = curriculum.structured_json.get("modules", [])
        
        # Look for Lesson 1 in Module 1 (or search by title)
        target_title_part = "Welcome and Module Overview"
        
        found = False
        for m_idx, m in enumerate(modules):
            lessons = m.get("lessons", [])
            for l_idx, l in enumerate(lessons):
                if target_title_part in l.get("title", ""):
                    found = True
                    print(f"FOUND LESSON: {l.get('title')}")
                    print("-" * 50)
                    print(f"Target Outcome (learning_objective): {l.get('learning_objective', 'MISSING')}")
                    print(f"Transcript Text Hash: {len(l.get('transcript_text', ''))} chars")
                    print(f"Source Clips: {l.get('source_clips', 'MISSING')}")
                    print("-" * 50)
                    print("Full JSON snippet:")
                    print(json.dumps(l, indent=2))
                    return

        if not found:
            print(f"Could not find lesson containing '{target_title_part}'")

    finally:
        db.close()

if __name__ == "__main__":
    debug_lesson_content()
