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
                
                # FORCE OVERWRITE for refinement
                # Only skipping if we already have the NEW high-quality structure (heuristic: check if questions < 1 for intro)
                # For now, let's just re-run everything to be safe.
                
                script = lesson.get("voiceover_script", "")
                if not script:
                    print(f"  [Skip] No script for: {title}")
                    continue
                    
                print(f"  [Gen] Generating Critical Quiz for: {title}...")
                
                try:
                    quiz_prompt = f"""
                    You are a Senior Utility Operations Trainer. 
                    Your students are "Work Order Clerks" who manage data for Utility Pole repairs.
                    
                    The Lesson Script below teaches general concepts (e.g. "Reactive Maintenance"), 
                    but you must apply them to the specific job of **Utility Pole Inspection**.
                    
                    Script: "{script}"
                    
                    Task:
                    Generate a "Job-Critical" multiple-choice quiz.
                    
                    Strict Guide:
                    1. SCENARIO REQD: "A field agent sends a photo of [XYZ Defect]. How do you handle this?"
                    2. APPLY CONCEPTS: If script defines "Reactive", ask: "Use the 'Reactive' type for which situation? (A) Snapped Crossarm (B) Scheduled Paint..."
                    3. FOCUS ON DATA: Ask about Priority Level, Safety Flags, and Labor Estimates.
                    4. ROLE: The student is sitting at a desk processing requests.
                    
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

                except Exception as e:
                    print(f"  [Error] Failed to generate quiz for {title}: {e}")

            # Save incrementally after each module
            if updated_count > 0:
                print(f"  [Save] Committing module updates to DB...")
                plan.structured_json = data
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(plan, "structured_json")
                db.commit()
                print("  [Save] Committed.")

        print("Backfill complete.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(hydrate_quizzes())
