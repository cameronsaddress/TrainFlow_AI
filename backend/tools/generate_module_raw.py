import sys
import os
import asyncio
import json
import argparse
from typing import List, Literal, Optional, Union, Annotated
from pydantic import BaseModel, Field
from sqlalchemy.orm.attributes import flag_modified

sys.path.append("/app")

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services.llm import client

# --- Configuration ---
DOC_ID = 10
COURSE_ID = 4

# --- Pydantic Models (Mirrored/Imported for Parsing) ---
# We define them here or import to ensure we can parse the raw JSON into them 
# before converting to dicts for DB storage.

from app.models.rich_content import HybridLessonRichContent, ContentBlock

# Wrapper for list of lessons
class GeneratedLesson(HybridLessonRichContent):
    target_lesson_title: str = Field(description="The EXACT title of the lesson this content belongs to.")

class ModuleGenerationOutput(BaseModel):
    lessons: List[GeneratedLesson]

# --- Prompt with One-Shot Examples ---
BULK_CONTENT_PROMPT = """
You are an expert Technical Instructor for National Grid.
Your task is to transform raw technical source text into structured "Hyper-Learning" lessons.

You are provided with the ENTIRE source document text.

TARGET MODULE: {module_title}
MISSING LESSONS (Generate content for these):
{lesson_list_str}

INSTRUCTIONAL DESIGN RULES:
1.  **Map Content Correctly**: Search the text for the specific topics of each lesson.
2.  **Tables (CRITICAL)**: If the source text contains lists of data, voltage classes, or specs, you MUST create a `table` block.
    - Rows MUST be simple arrays of strings: `[["row1_col1", "row1_col2"], ["row2_col1", "row2_col2"]]`
3.  **Alerts**: Use `alert` blocks for safety warnings or compliance rules.
    - `alert_type` must be one of: "safety", "compliance", "critical_info", "tip", "warning"
4.  **Quizzes**: Create a `quiz` block for the most important concept in each lesson.
5.  **Voiceover**: Write a short, professional voiceover script for each lesson.

OUTPUT REQUIREMENT:
Return a JSON object containing a `lessons` list.
Each item must have `target_lesson_title` matching one of the requested titles.

EXAMPLE OUTPUT FORMAT:
{{
  "lessons": [
    {{
      "target_lesson_title": "Safety Defaults",
      "learning_objective": "Identify the standard safety defaults for overhead construction.",
      "voiceover_summary": "Always adhere to NESC standards. The most stringent rule applies.",
      "estimated_reading_time_minutes": 5,
      "key_takeaways": ["Follow NESC", "Use PPE", "Report hazards"],
      "content_blocks": [
        {{
          "type": "text",
          "content": "All construction must meet NESC standards."
        }},
        {{
          "type": "alert",
          "alert_type": "safety",
          "title": "High Voltage",
          "content": "Always treat lines as energized."
        }},
        {{
            "type": "table",
            "title": "Clearance Distances",
            "headers": ["Voltage", "Distance"],
            "rows": [
                ["15kV", "10ft"],
                ["35kV", "15ft"]
            ]
        }},
        {{
            "type": "quiz",
            "title": "Safety Check",
            "question": "What standard applies?",
            "options": [
                {{ "text": "NESC", "is_correct": true, "explanation": "It is the national code." }},
                {{ "text": "Local Newspaper", "is_correct": false, "explanation": "Not a standard." }},
                {{ "text": "Guesswork", "is_correct": false, "explanation": "Never guess." }}
            ]
        }}
      ]
    }}
  ]
}}
"""

async def generate_and_consume(course_id: int, module_index: int):
    print(f"--- STARTING GENERATION & CONSUMPTION: Module Index {module_index} ---")
    db = SessionLocal()
    try:
        # Load Data
        course = db.query(k_models.HybridCurriculum).get(course_id)
        doc = db.query(k_models.KnowledgeDocument).get(DOC_ID)
        full_text = doc.extracted_text
        
        # Get Module
        modules = course.structured_json.get("modules", [])
        if module_index >= len(modules):
            print(f"Error: Module index {module_index} out of range (Total: {len(modules)})")
            return

        target_mod = modules[module_index]
        module_title = target_mod["title"]
        print(f"Target Module: {module_title}")

        # Collect Lessons
        lessons_to_generate = []
        for lesson in target_mod.get("lessons", []):
            lessons_to_generate.append(lesson["title"])

        if not lessons_to_generate:
            print("No lessons found in this module.")
            return

        print(f"Generating content for {len(lessons_to_generate)} lessons:\n" + "\n".join(f"- {t}" for t in lessons_to_generate))

        # Configuration
        BATCH_SIZE = 3
        
        # Split into chunks
        lesson_chunks = [lessons_to_generate[i:i+BATCH_SIZE] for i in range(0, len(lessons_to_generate), BATCH_SIZE)]
        
        print(f"Split {len(lessons_to_generate)} lessons into {len(lesson_chunks)} batches (Size {BATCH_SIZE}).")

        dump_dir = "/app/dumps"
        os.makedirs(dump_dir, exist_ok=True)

        for batch_idx, current_batch in enumerate(lesson_chunks):
            print(f"\n--- Processing Batch {batch_idx + 1}/{len(lesson_chunks)} ---")
            print("Lessons: " + ", ".join(current_batch))
            
            output_path = os.path.join(dump_dir, f"module_{module_index}_batch_{batch_idx}.txt")

            # LLM Call
            prompt = BULK_CONTENT_PROMPT.format(
                module_title=module_title,
                lesson_list_str="\n".join(f"- {t}" for t in current_batch)
            )

            print("Sending request to LLM (Grok 4.1 Fast)...")
            
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"SOURCE TEXT (ENTIRE DOCUMENT):\n{full_text}"}
            ]

            try:
                # Use the underlying client directly
                response = await client.chat.completions.create(
                    model="x-ai/grok-4.1-fast", 
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=30000 
                )
                
                raw_content = response.choices[0].message.content
                print(f"Received {len(raw_content)} chars from LLM.")
                
                # 1. Write Raw Dump
                with open(output_path, "w") as f:
                    f.write(raw_content)
                print(f"SUCCESS: Raw content written to {output_path}")

                # 2. Parse & Validate
                print("Parsing JSON response...")
                
                # We use the Pydantic model to validate structure
                parsed_data = ModuleGenerationOutput.model_validate_json(raw_content)
                print(f"Validation Valid! Found {len(parsed_data.lessons)} lessons.")

                # 3. Update Database
                print("Updating Database Records...")
                generated_map = {l.target_lesson_title: l for l in parsed_data.lessons}
                updates_count = 0
                
                # IMPORTANT: SQLAlchemy JSON mutation requires flag_modified
                # We must re-fetch course structure freshly every batch to avoid overwrites if using same object?
                # Actually, we are mutating the same list object in memory relative to the session. 
                # But safer to re-read 'structured_json' from the detailed object
                
                current_struct = course.structured_json
                current_modules = current_struct["modules"]
                target_mod_in_struct = current_modules[module_index]
                
                for lesson in target_mod_in_struct["lessons"]:
                    title = lesson["title"]
                    # Only process lessons in this batch/map
                    if title not in generated_map and not any(k.lower() in title.lower() for k in generated_map):
                         continue

                    gen_data = generated_map.get(title)
                    
                    # Fuzzy fallback
                    if not gen_data:
                        for k, v in generated_map.items():
                            if k.lower() in title.lower() or title.lower() in k.lower():
                                gen_data = v
                                break
                    
                    if gen_data:
                        # print(f" Updating: {title}")
                        rich_dict = gen_data.model_dump()
                        
                        lesson["status"] = "complete"
                        lesson["voiceover_script"] = rich_dict.get("voiceover_summary", "")
                        lesson["learning_objective"] = rich_dict.get("learning_objective", "")
                        lesson["estimated_reading_time_minutes"] = rich_dict.get("estimated_reading_time_minutes", 5)
                        lesson["key_takeaways"] = rich_dict.get("key_takeaways", [])
                        lesson["content_blocks"] = rich_dict.get("content_blocks", [])
                        
                        # Default PDF Ref
                        lesson["pdf_reference"] = {
                            "document_id": DOC_ID,
                            "page_number": 1, 
                            "label": "Source Document",
                            "anchor_text": title 
                        }
                        
                        updates_count += 1
                    else:
                        print(f" WARNING: No content generated for '{title}'")

                if updates_count > 0:
                    course.structured_json = current_struct # Re-assign
                    flag_modified(course, "structured_json")
                    db.commit()
                    print(f"SUCCESS: Database updated with {updates_count} lessons.")
                    # Re-refresh course to ensure latest state for next loop? 
                    # db.refresh(course) # Not strictly needed if we update the obj, but safe.
                    db.refresh(course)
                else:
                    print("No matching lessons found to update in this batch.")

            except Exception as e:
                print(f"ERROR in Batch {batch_idx}: {e}")
                # We continue to next batch instead of crashing completely?
                # No, let's log and continue
                import traceback
                traceback.print_exc()

    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate and Consume module content")
    parser.add_argument("--course-id", type=int, default=4, help="Course ID")
    parser.add_argument("--module-index", type=int, required=True, help="Module Index (0-based)")
    
    args = parser.parse_args()
    
    asyncio.run(generate_and_consume(args.course_id, args.module_index))
