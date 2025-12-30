import asyncio
import os
import json
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent dir to path to import app modules if needed, 
# but we can also just use direct SQL for simplicity like the plan implies for updates,
# or reuse the app's db connection if we are running inside the container.
# The user runs these with `docker exec ... python3 /app/tools/script.py`.
# So /app is in pythonpath usually.

sys.path.append('/app')

from app.services.llm import generate_text
from app.db import SessionLocal

# Setup DB connection
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ALIGNMENT_PROMPT = """
You are a helpful researcher.
We have a list of Lessons from a training course, including their Title, Target Outcome, and a short Summary.
Your job is to find the BEST EFFORT page number in the source PDF text where this lesson is likely located.

Input:
1. List of Lessons (Title, Objective, context).
2. PDF Text Chunk.

Instructions:
- Look for the Lesson Title in the text.
- If the exact title is not found, look for valid matches based on the 'Target Outcome' and 'Summary'.
- Use the page numbers usually found at the top or bottom of pages in the text (e.g. "Page 5" or just "5" surrounded by lines/headers).
- If you find a match, return the integer page number.
- If you are < 50% confident, do NOT include it.

Output Format:
Return a JSON object mapping Lesson Title to Page Number (Integer).
{{
    "Foreword and Purpose...": 4,
    "Copyright Notice...": 5
}}

Lessons:
{lessons_json}

PDF Text Chunk:
{pdf_text}
"""

async def main():
    print("Starting PDF Page Alignment (Fuzzy Mode)...")
    db = SessionLocal()
    
    try:
        # 1. Fetch PDF Text (ID 10)
        print("Fetching PDF text...")
        pdf_doc = db.execute(text("SELECT extracted_text FROM knowledge_documents WHERE id = 10")).fetchone()
        if not pdf_doc or not pdf_doc[0]:
            print("Error: PDF Document ID 10 not found or empty.")
            return
        
        full_text = pdf_doc[0]
        total_len = len(full_text)
        print(f"PDF Text Length: {total_len} chars")
        
        # 2. Fetch Course Structure (ID 4)
        print("Fetching Hybrid Course 4...")
        course = db.execute(text("SELECT structured_json FROM hybrid_curricula WHERE id = 4")).fetchone()
        if not course or not course[0]:
            print("Error: Hybrid Course ID 4 not found.")
            return
            
        course_json = course[0] 
        
        # 3. Extract Lessons with Context
        lessons_data = []
        modules = course_json.get("modules", [])
        for m in modules:
            for l in m.get("lessons", []):
                # Extract context
                summary = ""
                if "content_blocks" in l and len(l["content_blocks"]) > 0:
                    for b in l["content_blocks"]:
                        if b.get("type") == "text":
                            summary = b.get("content", "")[:200] # First 200 chars
                            break
                
                lessons_data.append({
                    "title": l.get("title"),
                    "target_outcome": l.get("learning_objective", ""),
                    "summary": summary
                })
                
        print(f"Prepared {len(lessons_data)} lessons for alignment.")
        
        # 4. Split PDF into 2 Halves
        midpoint = total_len // 2
        chunk1 = full_text[:midpoint]
        chunk2 = full_text[midpoint:]
        
        print("Splitting PDF into 2 chunks for LLM...")
        
        # 5. Call LLM
        page_map = {}
        
        async def process_chunk(chunk_id, text_chunk):
            print(f"Sending Chunk {chunk_id} to Grok 4.1 Fast...")
            
            prompt = ALIGNMENT_PROMPT.format(
                lessons_json=json.dumps(lessons_data, indent=2),
                pdf_text=text_chunk
            )
            
            # Using 10k tokens output to be safe for JSON
            response_text = await generate_text(prompt, max_tokens=15000)
            
            try:
                # Basic cleanup
                clean_json = response_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                print(f"Chunk {chunk_id} returned {len(data)} matches.")
                return data
            except Exception as e:
                print(f"Error parsing JSON from Chunk {chunk_id}: {e}")
                return {}

        # Run both
        results1 = await process_chunk(1, chunk1)
        results2 = await process_chunk(2, chunk2)
        
        page_map.update(results1)
        page_map.update(results2)
        
        print(f"Total Fuzzy Matches: {len(page_map)}")
        
        # 6. Update Course Structure
        updated_count = 0
        for m in modules:
            for l in m.get("lessons", []):
                title = l.get("title")
                if title in page_map:
                    new_page = page_map[title]
                    
                    if "pdf_reference" not in l or l["pdf_reference"] is None:
                        l["pdf_reference"] = {}
                    
                    l["pdf_reference"]["page_number"] = new_page
                    if "document_id" not in l["pdf_reference"]:
                         l["pdf_reference"]["document_id"] = 10
                         
                    updated_count += 1
        
        print(f"Updated {updated_count} lessons in memory.")
        
        # 7. Save back to DB
        print("Saving to database...")
        db.execute(
            text("UPDATE hybrid_curricula SET structured_json = :json_data WHERE id = 4"),
            {"json_data": json.dumps(course_json)}
        )
        db.commit()
        print("Database updated successfully.")
        
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
