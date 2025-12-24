import sys
import os
import json

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models

def audit():
    db = SessionLocal()
    try:
        curriculum = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        if not curriculum:
            print("No curriculum found.")
            return

        print(f"AUDIT REPORT for Curriculum ID {curriculum.id}: {curriculum.title}")
        print("-" * 120)
        print(f"{'Mod #':<6} | {'Title':<60} | {'Lessons':<8} | {'Source Videos'}")
        print("-" * 120)
        
        modules = curriculum.structured_json.get("modules", [])
        total_lessons = 0
        
        for i, m in enumerate(modules):
            lessons = m.get("lessons", [])
            count = len(lessons)
            total_lessons += count
            title = m.get("title", "N/A")[:58]
            sources = str(m.get("recommended_source_videos", []))
            
            print(f"{i+1:<6} | {title:<60} | {count:<8} | {sources}")
            
        print("-" * 120)
        print(f"TOTAL MODULES: {len(modules)}")
        print(f"TOTAL LESSONS: {total_lessons}")
        print("-" * 120)
        
    finally:
        db.close()

if __name__ == "__main__":
    audit()
