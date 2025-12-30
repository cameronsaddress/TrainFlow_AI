
import sys
import os
import json
import asyncio
from typing import List, Dict

# Setup paths
sys.path.append('/app')

from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
from app.models.knowledge import HybridCurriculum
from app.services.llm import generate_structure

# DB Connection
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@trainflow-db:5432/trainflow"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

COURSE_ID = 4
PDF_PATH = "/app/data/knowledge/184c1456-e663-4a6d-9505-895afb3b024c.pdf"

async def main():
    db = SessionLocal()
    try:
        # 1. Fetch Course & Lessons
        print(f"Fetching Course {COURSE_ID}...")
        course = db.query(HybridCurriculum).filter(HybridCurriculum.id == COURSE_ID).first()
        if not course:
            print("Course not found!")
            return

        json_data = course.structured_json
        modules = json_data.get('modules', [])
        all_titles = []
        
        print("Extracting Lesson Titles...")
        for m_idx, mod in enumerate(modules):
            for l_idx, lesson in enumerate(mod.get('lessons', [])):
                title = lesson.get('title')
                all_titles.append(title)
                
        print(f"Found {len(all_titles)} lessons.")

        # 2. Extract PDF Text with Page Markers
        print(f"Reading PDF and Extracting Text (this may take 1-2 mins)...")
        if not os.path.exists(PDF_PATH):
            print("PDF File NOT found!")
            return
            
        reader = PdfReader(PDF_PATH)
        full_text_with_pages = ""
        total_pages = len(reader.pages)
        
        # Optimization: Don't send 100% of text if huge. 
        # But user requested "Full PDF". We stick to text extraction.
        # Format: "Page 1: [Text...]"
        
        for i, page in enumerate(reader.pages):
            page_num = i + 1
            text = page.extract_text()
            if text:
                # Basic cleanup
                clean_text = " ".join(text.split())
                full_text_with_pages += f"\n[PAGE {page_num}]\n{clean_text}\n"
            
            if i % 100 == 0:
                print(f"Extracted {page_num}/{total_pages}...")

        print(f"Total Text Length: {len(full_text_with_pages)} chars.")
        
        # 3. Construct LLM Prompt
        system_prompt = """
        You are a Document Indexer.
        Your Task: Map each Lesson Title to the EXACT PAGE NUMBER where it begins in the provided manual.
        
        Input:
        1. List of Lesson Titles.
        2. Full Manual Text with [PAGE X] markers.
        
        Rules:
        - Return a JSON object with a "mappings" list.
        - Each mapping must have "title" (exact match) and "page_number" (integer).
        - If a title is not found, omit it or set page_number to null.
        - Use fuzzy matching for titles (e.g. "Intro to X" matches "Section 1: Introduction to X").
        - IMPORTANT: The page number must come from the [PAGE X] marker immediately preceding the text match.
        
        Output Schema:
        {
            "mappings": [
                { "title": "Lesson Title Here", "page_number": 42 },
                ...
            ]
        }
        """
        
        user_content = f"""
        LESSON TITLES TO FIND:
        {json.dumps(all_titles, indent=2)}
        
        MANUAL CONTENT:
        {full_text_with_pages}
        """

        print("Sending to Grok (x-ai/grok-4.1-fast)...")
        
        response = await generate_structure(
            system_prompt=system_prompt,
            user_content=user_content,
            model="x-ai/grok-4.1-fast",
            max_tokens=60000 
        )
        
        # 4. Handle Response & Update DB
        if not response or "mappings" not in response:
            print("Error: Invalid or empty response from LLM.")
            print(f"Raw Response: {response}")
            return

        mappings = response.get("mappings", [])
        print(f"Received {len(mappings)} mappings.")
        
        # Create lenient lookup dict
        title_to_page = {}
        for m in mappings:
            # Handle potential key variations if LLM slips up
            t = m.get("title") or m.get("Title")
            p = m.get("page_number") or m.get("Page_Number") or m.get("page")
            
            if t and p is not None:
                title_to_page[t] = p

        print("Updating Database...")
        update_count = 0
        
        for mod in modules:
            for lesson in mod.get('lessons', []):
                t = lesson.get('title')
                
                # Check exact or fuzzy match in our lookup
                matched_page = title_to_page.get(t)
                
                if matched_page:
                    if 'pdf_reference' not in lesson or not lesson['pdf_reference']:
                         lesson['pdf_reference'] = {}
                    
                    try:
                        new_p = int(matched_page)
                        old_p = lesson['pdf_reference'].get('page_number')
                        
                        if old_p != new_p:
                            lesson['pdf_reference']['page_number'] = new_p
                            print(f"UPDATED: '{t[:30]}...' {old_p} -> {new_p}")
                            update_count += 1
                    except ValueError:
                         print(f"Skipping invalid page number: {matched_page}")

        if update_count > 0:
            course.structured_json = {"modules": modules} # Re-assign dict to ensure update
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(course, "structured_json")
            
            db.commit()
            print(f"SUCCESS: Committed {update_count} page updates.")
        else:
            print("No updates needed or no matches found.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
