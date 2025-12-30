import sys
sys.path.append("/app")

import asyncio
from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services.llm import generate_structure_validated
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.orm.attributes import flag_modified

# --- Configuration ---
DOC_ID = 10
COURSE_ID = 4
TARGET_MODULE_KEYWORDS = ["Section 1", "General"]

# --- Imported Models ---
from app.models.rich_content import HybridLessonRichContent

# --- Bulk Wrapper Model ---
class LessonContentResult(HybridLessonRichContent):
    target_lesson_title: str = Field(description="The EXACT title of the lesson this content belongs to.")

class BulkModuleGeneration(BaseModel):
    lessons: List[LessonContentResult] = Field(description="List of rich content for each lesson in the module.")

# --- Prompt ---
BULK_CONTENT_PROMPT = """
You are an expert Technical Instructor for National Grid.
Your task is to transform raw technical source text into structured "Hyper-Learning" lessons.

You are provided with the ENTIRE source document text.

TARGET MODULE: Section 1 – General
MISSING LESSONS (Generate content for these):
{lesson_list_str}

INSTRUCTIONAL DESIGN RULES:
1.  **Map Content Correctly**: Search the text for the specific topics of each lesson.
2.  **Tables (CRITICAL)**: If the source text contains lists of data, voltage classes, or specs, you MUST create a `table` block.
3.  **Alerts**: Use `alert` blocks for safety warnings or compliance rules.
4.  **Quizzes**: Create a `quiz` block for the most important concept in each lesson.
5.  **Voiceover**: Write a short, professional voiceover script for each lesson.
6.  **PDF References**: We will handle page linking programmatically.

OUTPUT REQUIREMENT:
Return a JSON object containing a list of `lessons`.
Each item must have `target_lesson_title` matching one of the requested titles.
"""

async def main():
    db = SessionLocal()
    try:
        print("--- BULK HYPER-LEARNING GENERATION (RETRY PENDING) ---")
        
        course = db.query(k_models.HybridCurriculum).get(COURSE_ID)
        doc = db.query(k_models.KnowledgeDocument).get(DOC_ID)
        full_text = doc.extracted_text
        print(f"Loaded Full PDF Text: {len(full_text)} chars.")
        
        # Identify Target Module
        target_struct_mod = None
        target_mod_idx = -1
        struct = course.structured_json
        for i, mod in enumerate(struct["modules"]):
            if all(k in mod["title"] for k in TARGET_MODULE_KEYWORDS):
                target_struct_mod = mod
                target_mod_idx = i
                break
        
        if not target_struct_mod:
            print("Error: Target module not found.")
            return

        # Identify Pending Lessons
        pending_lessons = []
        for lesson in target_struct_mod["lessons"]:
            # Check if status is pending OR content is empty (to catch failed runs)
            if lesson.get("status") != "complete" or not lesson.get("content_blocks"):
                pending_lessons.append(lesson["title"])
        
        if not pending_lessons:
            print("All lessons in Section 1 are already complete!")
            return
            
        print(f"Found {len(pending_lessons)} pending lessons:")
        for t in pending_lessons:
            print(f" - {t}")

        # Limit batch size if too many (e.g. max 3 at a time to ensure completion)
        # 3k output tokens is likely enough for 3 lessons (~1k each)
        BATCH_SIZE = 3
        
        # Process in chunks
        current_batch = pending_lessons[:BATCH_SIZE]
        print(f"Processing Batch of {len(current_batch)}: {current_batch}")

        print("Executing LLM generation...")
        response = await generate_structure_validated(
            system_prompt=BULK_CONTENT_PROMPT.format(
                lesson_list_str="\n".join(f"- {t}" for t in current_batch),
            ),
            user_content=f"SOURCE TEXT (ENTIRE DOCUMENT):\n{full_text}",
            model_class=BulkModuleGeneration,
            model="x-ai/grok-4.1-fast",
            max_retries=2
        )
        
        print(f"Generation Complete. Received {len(response.lessons)} items.")

        # Update Database
        generated_map = {l.target_lesson_title: l for l in response.lessons}
        updates_count = 0
        current_modules = struct["modules"]
        target_mod = current_modules[target_mod_idx]
        
        for lesson in target_mod["lessons"]:
            title = lesson["title"]
            if title not in current_batch:
                continue
                
            gen_data = generated_map.get(title)
            # Fuzzy fallback
            if not gen_data:
                for k, v in generated_map.items():
                    if k.lower() in title.lower() or title.lower() in k.lower():
                        gen_data = v
                        break
            
            if gen_data:
                print(f"Updating Lesson: {title}")
                rich_dict = gen_data.model_dump()
                
                lesson["status"] = "complete"
                lesson["voiceover_script"] = rich_dict.get("voiceover_summary", "")
                lesson["learning_objective"] = rich_dict.get("learning_objective", "")
                lesson["estimated_reading_time_minutes"] = rich_dict.get("estimated_reading_time_minutes", 5)
                lesson["key_takeaways"] = rich_dict.get("key_takeaways", [])
                lesson["content_blocks"] = rich_dict.get("content_blocks", [])
                
                new_clips = rich_dict.get("source_clips", [])
                if new_clips:
                    lesson["source_clips"] = new_clips
                
                # Set PDF Reference
                lesson["pdf_reference"] = {
                     "document_id": DOC_ID,
                     "page_number": 1, 
                     "label": "Source Document",
                     "anchor_text": title 
                }
                
                updates_count += 1
            else:
                print(f"WARNING: No content generated for '{title}'")

        if updates_count > 0:
            struct["modules"] = current_modules
            course.structured_json = struct
            flag_modified(course, "structured_json")
            db.commit()
            print(f"SUCCESS: Updated {updates_count} lessons.")
        else:
            print("No updates made this batch.")

    except Exception as e:
        print(f"Script Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
