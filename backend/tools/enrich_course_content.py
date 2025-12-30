import os
import sys
import json
import asyncio
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy import text
from pydantic import BaseModel, Field

# Setup path
sys.path.append("/app")
from app.db import SessionLocal
from app.models.knowledge import HybridCurriculum, KnowledgeDocument

load_dotenv()

# Configuration
COURSE_ID = 4
PDF_DOC_ID = 10
MODEL_NAME = "x-ai/grok-4.1-fast"
MAX_TOKENS = 30000

# --- Pydantic Models for Active Mastery Results ---
class ComplianceRule(BaseModel):
    rule: str = Field(description="The specific rule (must/shall). Ex: 'Reflectors required < 6ft from road'")

class QuizQuestion(BaseModel):
    text: str = Field(description="The question text asking about a specific data point.")
    correct_answer: str = Field(description="The correct answer.")
    options: List[str] = Field(description="3-4 distinct options including the correct one.")
    explanation: str = Field(description="Why this is the answer.")

class Scenario(BaseModel):
    setup: str = Field(description="A realistic job site situation.")
    question: str = Field(description="What should you do?")
    correct_action: str = Field(description="The compliant action to take.")
    reasoning: str = Field(description="The rule that applies here.")

class ActiveMasteryContent(BaseModel):
    compliance_checklist: List[ComplianceRule]
    flash_challenge: List[QuizQuestion]
    scenario_sim: List[Scenario]

# --- Helpers ---
def get_db():
    return SessionLocal()

def fetch_pdf_text(db) -> str:
    print("Fetching PDF text...")
    res = db.execute(text(f"SELECT extracted_text FROM knowledge_documents WHERE id = {PDF_DOC_ID}")).fetchone()
    if not res:
        raise ValueError(f"Document {PDF_DOC_ID} not found")
    return res[0]

def extract_page_content(full_text: str, target_page: int) -> str:
    """
    Tries to locate the specific page content using heuristics.
    """
    # Heuristic 1: Look for "Page X" markers
    # We look for Page X and Page X+1
    
    # Try multiple patterns for page headers/footers
    patterns = [
        f"Page {target_page}",
        f"\n{target_page}\n",
        f" {target_page} "
    ]
    
    start_idx = -1
    for p in patterns:
        idx = full_text.find(p)
        if idx != -1:
            start_idx = idx
            break
            
    if start_idx == -1:
        # Fallback: estimate location
        # total_pages approx 200? average 2500 chars/page?
        # This is risky, but better than nothing.
        # Let's assume ~3000 chars per page
        start_idx = (target_page - 1) * 3000
    
    # Find end (Page X+1)
    next_page = target_page + 1
    end_idx = -1
    
    next_patterns = [
        f"Page {next_page}",
        f"\n{next_page}\n",
        f" {next_page} "
    ]
    
    for p in next_patterns:
        idx = full_text.find(p, start_idx + 100) # +100 to avoid matching same location if fuzzy
        if idx != -1:
            end_idx = idx
            break
            
    if end_idx == -1:
        end_idx = start_idx + 4000 # Take 4000 chars if end not found
        
    # Clamp
    if end_idx > len(full_text): 
        end_idx = len(full_text)
        
    return full_text[start_idx:end_idx]

async def enrich_lesson(client: AsyncOpenAI, lesson_title: str, pdf_text: str) -> Optional[ActiveMasteryContent]:
    print(f"Enriching '{lesson_title}'...")
    
    sys_prompt = (
        "You are an expert Technical Compliance Trainer.\n"
        "Input: Raw technical PDF text.\n"
        "Task: Generate 3 Active Learning modules to ensure the trainee MASTERS this content.\n"
        "RETURN JSON WITH THESE EXACT KEYS:\n"
        "1. 'compliance_checklist': List of 3-5 'Must/Shall' rules (objects with 'rule' field).\n"
        "2. 'flash_challenge': List of 2-3 multiple choice questions (objects with 'text', 'correct_answer', 'options', 'explanation').\n"
        "3. 'scenario_sim': List of 1 realistic scenario (object with 'setup', 'question', 'correct_action', 'reasoning').\n"
        "Ensure the output matches the Pydantic schema exactly."
    )
    
    user_prompt = f"PDF CONTENT:\n{pdf_text}\n\nGenerate Active Mastery Modules JSON."
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2, # Low temp for factual accuracy
            max_tokens=20000,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        return ActiveMasteryContent(**data)
        
    except Exception as e:
        print(f"LLM Error for {lesson_title}: {e}")
        return None

async def process_lesson_batch(db, course, lessons_to_process: List[Dict], client: AsyncOpenAI, full_pdf_text: str, sem: asyncio.Semaphore):
    tasks = []
    
    async def worker(lesson_data):
        async with sem:
            l = lesson_data['lesson']
            title = l.get("title")
            
            # Skip if already enriched (Check for compliance_checklist)
            if "content_blocks" in l:
                if any(b.get("type") == "compliance_checklist" for b in l["content_blocks"]):
                    # print(f"Skipping {title} (Already Enriched)")
                    return False

            if "pdf_reference" not in l or "page_number" not in l["pdf_reference"]:
                return False
                
            page_num = l["pdf_reference"]["page_number"]
            lesson_text = extract_page_content(full_pdf_text, page_num)
            
            if len(lesson_text) < 100:
                print(f"Skipping {title} (Text too short)")
                return False

            enrichment = await enrich_lesson(client, title, lesson_text)
            
            if enrichment:
                # 1. Compliance Checklist
                checklist_block = {
                    "type": "compliance_checklist",
                    "title": "Critical Requirements (Must Acknowledge)",
                    "items": [r.rule for r in enrichment.compliance_checklist]
                }
                
                # 2. Flash Challenge
                quiz_blocks = []
                for q in enrichment.flash_challenge:
                    quiz_blocks.append({
                        "type": "quiz",
                        "question": q.text,
                        "options": [{"text": opt, "is_correct": (opt == q.correct_answer), "explanation": q.explanation} for opt in q.options]
                    })
                    
                # 3. Scenario
                scenario_block = None
                if enrichment.scenario_sim:
                    s = enrichment.scenario_sim[0]
                    scenario_block = {
                        "type": "scenario",
                        "setup": s.setup,
                        "question": s.question,
                        "answer": s.correct_action,
                        "reasoning": s.reasoning
                    }
                
                # Append to content_blocks
                if "content_blocks" not in l:
                    l["content_blocks"] = []
                    
                # Insert intelligently
                l["content_blocks"].insert(min(1, len(l["content_blocks"])), checklist_block)
                l["content_blocks"].extend(quiz_blocks)
                if scenario_block:
                    l["content_blocks"].append(scenario_block)
                    
                print(f"ENRICHED: {title} ({len(quiz_blocks)} quizzes)")
                return True
            return False

    for item in lessons_to_process:
        tasks.append(worker(item))
        
    results = await asyncio.gather(*tasks)
    return sum(results)

async def main():
    print("Starting Optimized Course Content Enrichment (Parallel + Incremental)...")
    db = get_db()
    
    try:
        full_pdf_text = fetch_pdf_text(db)
        client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_API_BASE")
        )
        
        sem = asyncio.Semaphore(5) # Process 5 lessons at a time
        
        # Reload fresh from DB
        course = db.query(HybridCurriculum).filter(HybridCurriculum.id == COURSE_ID).first()
        j = course.structured_json
        
        all_lessons = []
        for m_idx, m in enumerate(j.get("modules", [])):
            for l_idx, l in enumerate(m.get("lessons", [])):
                all_lessons.append({
                    "lesson": l, 
                    "m_idx": m_idx, 
                    "l_idx": l_idx
                })
        
        print(f"Total Lessons to check: {len(all_lessons)}")
        
        # Chunk into batches of 10 for saving
        batch_size = 10
        total_enriched = 0
        
        for i in range(0, len(all_lessons), batch_size):
            batch = all_lessons[i : i + batch_size]
            print(f"Processing Batch {i//batch_size + 1}/{len(all_lessons)//batch_size + 1}...")
            
            enriched_count = await process_lesson_batch(db, course, batch, client, full_pdf_text, sem)
            
            if enriched_count > 0:
                # Commit Batch
                course.structured_json = j
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(course, "structured_json")
                db.commit()
                # Refresh to avoid stale object issues (optional, but safer to re-query if needed, though here we hold reference to j dict)
                print(f"Saved Batch ({enriched_count} new updates). Total so far: {total_enriched + enriched_count}")
                total_enriched += enriched_count
            else:
                print("Batch processed (No new updates).")
                
        print(f"DONE. Total Lessons Enriched in this run: {total_enriched}")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
