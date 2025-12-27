import asyncio
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import llm

async def hydrate_quizzes():
    db = SessionLocal()
    try:
        # Get latest curriculum
        plan = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        if not plan:
            print("No curriculum found.")
            return

        print(f"Hydrating Quizzes for: {plan.title} (ID: {plan.id})")
        
        data = plan.structured_json
        modules = data.get("modules", [])
        
        updated_count = 0
        
        for m_idx, module in enumerate(modules):
            lessons = module.get("lessons", [])
            for l_idx, lesson in enumerate(lessons):
                title = lesson.get("title", f"Lesson {l_idx}")
                
                # Check if quiz exists
                if "quiz" in lesson and lesson["quiz"] and lesson["quiz"].get("questions"):
                    print(f"  [Skip] Quiz exists for: {title}")
                    continue
                    
                script = lesson.get("voiceover_script", "")
                if not script:
                    print(f"  [Skip] No script for: {title}")
                    continue
                    
                print(f"  [Gen] Generating Quiz for: {title}...")
                
                try:
                    quiz_prompt = f"""
                    Based on the Lesson Script below, generate a multiple-choice quiz to test understanding.
                    
                    Script: "{script}"
                    
                    Requirements:
                    1. Identify the most critical concepts.
                    2. Create multiple-choice questions (max 15, but use fewer if appropriate).
                    3. Provide 3-4 options per question.
                    4. Indicate the correct answer and a brief explanation.
                    
                    Output JSON:
                    {{
                      "questions": [
                        {{
                          "question": "...",
                          "options": ["Option A", "Option B", "Option C"],
                          "correct_answer": "Option A",
                          "explanation": "..."
                        }}
                      ]
                    }}
                    """
                    
                    quiz_data = await llm.generate_structure(
                        system_prompt="You are an Instructional Designer. Create a knowledge check quiz.",
                        user_content=quiz_prompt,
                        model="x-ai/grok-4.1-fast"
                    )
                    
                    lesson["quiz"] = quiz_data
                    updated_count += 1
                    
                    # Save progress iteratively (or batch, but this is safer for long runs)
                    # Actually, we should save at the end or per module to avoid thrashing
                    
                except Exception as e:
                    print(f"  [Error] Failed to generate quiz for {title}: {e}")

        if updated_count > 0:
            print(f"Saving {updated_count} new quizzes to DB...")
            # Update the JSON column
            plan.structured_json = data
            
            # Force update (SQLAlchemy tracks JSON changes but let's be explicit)
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(plan, "structured_json")
            
            db.commit()
            print("Done!")
        else:
            print("No updates needed.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(hydrate_quizzes())
