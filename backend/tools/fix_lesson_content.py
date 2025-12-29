import sys
sys.path.append("/app")
import asyncio
from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services.llm import generate_structure_validated
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm.attributes import flag_modified

# --- Configuration ---
DOC_ID = 10
COURSE_ID = 4
TARGET_MODULE_TITLE = "Section 1 – General"
TARGET_LESSON_TITLE = "Transmission and Sub-Transmission Voltages"

# --- Models ---
from app.models.rich_content import HybridLessonRichContent, TextBlock, TableBlock, AlertBlock, QuizBlock

# --- Prompt ---
CONTENT_PROMPT = """
You are an expert Technical Instructor for National Grid.
Your task is to transform raw technical source text into a "Hyper-Learning" structured lesson.
You must break the content down into specific BLOCKS: Tables for data, Alerts for rules, Quizzes for checks, and Text for explanation.

LESSON TITLE: {lesson_title}
MODULE CONTEXT: {module_title}

SOURCE TEXT:
{source_text}

INSTRUCTIONAL DESIGN RULES:
1.  **Tables (CRITICAL)**: If the source text contains lists of data (like Voltage Classes, clearances, or equipment ratings), you MUST create a `table` block. Do not write this as text.
    *   Example: For "Transmission Voltages", create columns like [Voltage Class, System Type, Comments].
2.  **Alerts**: If there are safety warnings, exclusions ("Does not apply to..."), or compliance mandates ("Must be..."), use an `alert` block.
    *   Type 'safety' for dangers.
    *   Type 'compliance' for rules/standards.
3.  **Definitions**: If technical terms are introduced, use a `definition` block.
4.  **Quizzes**: Insert a `quiz` block to test understanding of the *most important* concept in this section (e.g., "What is the lower limit for transmission voltage?").
5.  **Voiceover Summary**: Write a generated script for an AI narrator that summarizes this lesson in a conversational, professional tone (approx 1 minute).

OUTPUT REQUIREMENT:
Return a JSON object matching the `HybridLessonRichContent` schema.
Ensure `content_blocks` is a mix of Text, Table, Alert, Quiz, etc.

EXAMPLE JSON OUTPUT:
{{
  "learning_objective": "Understand transmission voltages.",
  "estimated_reading_time_minutes": 5,
  "voiceover_summary": "In this lesson...",
  "key_takeaways": ["Point 1", "Point 2"],
  "content_blocks": [
    {{
      "type": "text",
      "content": "Transmission voltages are high voltage..."
    }},
    {{
      "type": "table",
      "title": "Voltage Levels",
      "headers": ["Class", "Voltage"],
      "rows": [
        {{"values": ["Transmission", "345 kV"]}}
      ]
    }},
    {{
      "type": "alert",
      "alert_type": "safety",
      "title": "Warning",
      "content": "Always verify usage."
    }},
    {{
      "type": "quiz",
      "question": "What is the min voltage?",
      "options": [
        {{"text": "115 kV", "is_correct": true, "explanation": "This is correct."}},
        {{"text": "12 kV", "is_correct": false, "explanation": "Too low."}}
      ]
    }}
  ]
}}
"""

async def main():
    db = SessionLocal()
    try:
        print("--- TARGETED HYPER-LEARNING GENERATION ---")
        
        # 1. Fetch Course & Doc
        course = db.query(k_models.HybridCurriculum).get(COURSE_ID)
        doc = db.query(k_models.KnowledgeDocument).get(DOC_ID)
        full_text = doc.extracted_text
        
        # 2. Extract Content (Smart Anchor)
        # Look for body text: "This is a list of nominal transmission system voltages"
        start_idx = full_text.find("This is a list of nominal transmission system voltages")
        
        if start_idx != -1:
             start_idx = full_text.rfind("1.3 TRANSMISSION VOLTAGES", 0, start_idx) 
             end_idx = full_text.find("1.5 PRIMARY DISTRIBUTION VOLTAGES", start_idx)
             if end_idx == -1: end_idx = start_idx + 6000
        else:
             print("Warning: Content anchor not found. Using wide search.")
             start_idx = full_text.find("Section 1")
             end_idx = start_idx + 20000

        print(f"Slicing text from {start_idx} to {end_idx} ({end_idx-start_idx} chars)")
        context_text = full_text[start_idx:end_idx]

        # 3. Locate Lesson
        target_mod_idx = -1
        target_less_idx = -1
        target_lesson = None
        struct = course.structured_json
        
        for m_i, mod in enumerate(struct["modules"]):
            if "General" in mod["title"] or "Section 1" in mod["title"]:
                for l_i, less in enumerate(mod["lessons"]):
                    if "Transmission" in less["title"]:
                        target_mod_idx = m_i
                        target_less_idx = l_i
                        target_lesson = less
                        break
            if target_lesson: break
        
        if not target_lesson:
            print("Error: Target lesson not found.")
            return

        print("Executing LLM generation (Rich Content)...")
        
        # 4. Call LLM
        response = await generate_structure_validated(
            system_prompt=CONTENT_PROMPT.format(
                lesson_title=TARGET_LESSON_TITLE,
                module_title=TARGET_MODULE_TITLE,
                source_text=""
            ),
            user_content=f"SOURCE TEXT:\n{context_text}",
            model_class=HybridLessonRichContent,
            model="x-ai/grok-4.1-fast",
            max_retries=2
        )
        
        print(f"Generation Complete. Blocks: {len(response.content_blocks)}")
        for b in response.content_blocks:
            print(f" - {b.type}")

        # 5. Update DB (Serialize Pydantic to Dict)
        updated_lesson = target_lesson.copy()
        updated_lesson["status"] = "complete"
        # Dump the whole rich model to dict
        rich_data = response.model_dump()
        
        # Merge fields
        updated_lesson["voiceover_script"] = rich_data["voiceover_summary"] # Backwards compatibility
        updated_lesson["learning_objective"] = rich_data["learning_objective"]
        updated_lesson["estimated_reading_time_minutes"] = rich_data["estimated_reading_time_minutes"]
        updated_lesson["key_takeaways"] = rich_data["key_takeaways"]
        updated_lesson["content_blocks"] = rich_data["content_blocks"] 

        # --- Inject PDF Reference (Smart Page Find) ---
        # --- Inject PDF Reference (Dynamic Smart Lookup) ---
        try:
            # Dynamic Lookup: Find the page containing the exact section header
            # We use the known header for this specific lesson
            section_header = "1.3 TRANSMISSION VOLTAGES"
            print(f"Searching PDF for section: '{section_header}'...")
            
            chunk = db.query(k_models.KnowledgeChunk).filter(
                k_models.KnowledgeChunk.document_id == DOC_ID,
                k_models.KnowledgeChunk.content.ilike(f"%{section_header}%")
            ).first()
            
            if chunk and chunk.metadata_json:
                page_num = chunk.metadata_json.get("page_number", 1)
                rich_data["pdf_reference"] = {
                    "document_id": DOC_ID,
                    "page_number": page_num,
                    "label": f"Source: Page {page_num}",
                    "anchor_text": section_header # Store for runtime correction
                }
                updated_lesson["pdf_reference"] = rich_data["pdf_reference"]
                print(f"Linked PDF Reference: Page {page_num} (Dynamically Found, Anchor: '{section_header}')")
            else:
                 print("Warning: Section header not found in PDF chunks.")
        except Exception as e:
            print(f"Warning: Could not link PDF page: {e}")
        
        updated_lesson["content_blocks"] = rich_data["content_blocks"]
        
        struct["modules"][target_mod_idx]["lessons"][target_less_idx] = updated_lesson
        course.structured_json = struct
        flag_modified(course, "structured_json")
        db.commit()
        
        print("SUCCESS: Database updated with Rich Content.")

    except Exception as e:
        print(f"Script Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()



if __name__ == "__main__":
    asyncio.run(main())
