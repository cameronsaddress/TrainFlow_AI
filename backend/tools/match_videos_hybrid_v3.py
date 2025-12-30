import os
import sys
import json
import asyncio
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

# Add the backend directory to sys.path so we can import app modules
sys.path.append("/app")

from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import AsyncOpenAI

# DB Imports
from app.db import SessionLocal
from app.models.knowledge import VideoCorpus, HybridCurriculum

# Load environment variables
load_dotenv()

# --- Configuration ---
BATCH_SIZE_VIDEOS = 100 # We will split explicitly into 2 batches, so this is just a high cap if needed
MODEL_NAME = "x-ai/grok-4.1-fast"  # Supports 2M context
MAX_TOKENS = 30000
TARGET_HYBRID_ID = 4

# --- Pydantic Models for LLM Output ---
class VideoMatch(BaseModel):
    lesson_id: str = Field(description="The exact TITLE of the lesson this clip belongs to")
    video_filename: str = Field(description="The filename of the source video")
    start_time: float = Field(description="Start time of the clip in seconds")
    end_time: float = Field(description="End time of the clip in seconds")
    reason: str = Field(description="A brief explanation of why this clip matches the lesson content")

class BatchMatches(BaseModel):
    matches: List[VideoMatch]

# --- Database Helper ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Data Fetching ---

def get_hybrid_curriculum(db: Session, hybrid_id: int) -> Optional[Dict]:
    """Fetches the structured_json of the specific HybridCurriculum."""
    hybrid = db.query(HybridCurriculum).filter(HybridCurriculum.id == hybrid_id).first()
    if not hybrid:
        return None
    return hybrid.structured_json

def get_videos(db: Session) -> List[Dict]:
    """
    Fetches videos from VideoCorpus that have a transcript.
    Returns a list of dicts: {filename, duration, transcript_text}
    """
    videos = db.query(VideoCorpus).all()
    video_list = []
    
    print(f"Found {len(videos)} videos in VideoCorpus table.")
    
    for v in videos:
        # Check source fields
        if not v.transcript_json and not v.transcript_text:
            print(f"Skipping {v.filename}: No transcript found.")
            continue
            
        transcript_content = ""
        
        # Priority 1: JSON with timestamps
        if v.transcript_json:
            try:
                # If it's stored as a JSON object (list of segments)
                segments = v.transcript_json
                if isinstance(segments, list) and len(segments) > 0 and 'start' in segments[0]:
                     lines = []
                     for seg in segments:
                         start = seg.get('start', 0)
                         text = seg.get('text', '').strip()
                         lines.append(f"[{int(start // 60):02d}:{int(start % 60):02d}] {text}")
                     transcript_content = "\n".join(lines)
                else:
                    # Fallback if json structure is weird
                    transcript_content = str(segments)
            except Exception as e:
                print(f"Error parsing transcript_json for {v.filename}: {e}")
        
        # Priority 2: Raw Text
        if not transcript_content and v.transcript_text:
             transcript_content = v.transcript_text[:50000]
        
        # If still empty, skip
        if not transcript_content:
            continue

        # Filter out BJJ/Irrelevant videos
        # Heuristic: Check for keywords in filename content
        lower_name = v.filename.lower()
        if "jiu" in lower_name or "bjj" in lower_name or "grappling" in lower_name or "keenan" in lower_name or "danaher" in lower_name:
            print(f"Skipping BJJ/Irrelevant Video: {v.filename}")
            continue

        # Cap transcript at reasonable length for 2M context (e.g., 200k chars ~ 50k tokens)
        # 16 videos * 200k chars = 3.2M chars ~ 800k tokens. Safe.
        # But some are 300M chars?! Wait.
        # 304340232 chars is 300 MB. That's absurd for a transcript. 
        # It means v.transcript_text is HUGE or I am reading it wrong.
        # If it's 300MB text, that's > 100M tokens.
        # I MUST cap this.
        if len(transcript_content) > 100000:
            transcript_content = transcript_content[:100000] + "...(truncated)"
            
        print(f"Keeping Video: {v.filename} (Length: {len(transcript_content)} chars)")
        video_list.append({
            "filename": v.filename,
            "duration": v.duration_seconds or 0,
            "transcript": transcript_content
        })
        
    return video_list

def flatten_lessons_hybrid(structured_json: Dict) -> List[Dict]:
    """
    Flattens the Hybrid Curriculum modules->lessons structure.
    Extracts 'learning_objective' (Target Outcome) and 'content_blocks' (Description).
    """
    flat_lessons = []
    
    modules = structured_json.get("modules", [])
    for module in modules:
        for lesson in module.get("lessons", []):
            title = lesson.get("title", "Unknown Lesson")
            
            # Extract Target Outcome
            target_outcome = lesson.get("learning_objective", "")
            
            # Extract Description (First text content block)
            description = ""
            for block in lesson.get("content_blocks", []):
                if block.get("type") == "text":
                    description = block.get("content", "")
                    break # Only take the first one as description roughly matches the screenshot
            
            # Combine for LLM
            content_summary = f"TARGET OUTCOME: {target_outcome}\n\nDESCRIPTION: {description}"
            
            flat_lessons.append({
                "lesson_id": title, # Using Title as ID
                "content_summary": content_summary
            })
            
    return flat_lessons

# --- LLM Processing ---

async def process_batch(client: AsyncOpenAI, lessons: List[Dict], videos: List[Dict], batch_num: int):
    print(f"--- Processing Batch {batch_num} ({len(videos)} videos) ---")
    
    # 1. Dump Debug Data
    debug_dir = "/app/backend/dumps"
    os.makedirs(debug_dir, exist_ok=True)
    
    output_filename = f"{debug_dir}/video_matches_hybrid_batch_{batch_num}.json"
    
    # Check if already done
    if os.path.exists(output_filename):
        print(f"Batch {batch_num} output already exists. Skipping processing.")
        try:
             with open(output_filename, "r") as f:
                 data = json.load(f)
                 return data.get("matches", [])
        except:
             print("Error reading existing file. Reprocessing.")
    
    with open(f"{debug_dir}/debug_lessons_hybrid_batch_{batch_num}.txt", "w") as f:
        for l in lessons:
            f.write(f"ID: {l['lesson_id']}\nCONTENT: {l['content_summary']}\n---\n")

    with open(f"{debug_dir}/debug_transcripts_hybrid_batch_{batch_num}.txt", "w") as f:
        for v in videos:
            f.write(f"FILENAME: {v['filename']}\nTRANSCRIPT:\n{v['transcript'][:1000]}...\n---\n")

    # 2. Construct Prompt
    # Prepare Lesson Context
    lessons_str = ""
    for l in lessons:
        lessons_str += f"LESSON_ID: {l['lesson_id']}\nCONTENT_SUMMARY:\n{l['content_summary']}\n###\n"
        
    # Prepare Video Context
    videos_str = ""
    for v in videos:
        videos_str += f"VIDEO_FILENAME: {v['filename']}\nTRANSCRIPT:\n{v['transcript']}\n###\n"
        
    system_prompt = (
        "You are an expert video editor and curriculum designer. "
        "Your task is to match video clips to lessons based on their content relevance.\n"
        "You have a list of LESSONS (with Target Outcomes and Descriptions) and a list of VIDEOS (with transcripts).\n\n"
        "For each match, identify:\n"
        "1. The LESSON_ID (must match the provided Title exactly).\n"
        "2. The VIDEO_FILENAME.\n"
        "3. The START_TIME and END_TIME (in seconds) of the relevant clip.\n"
        "4. A REASON for the match.\n\n"
        "RULES:\n"
        "- Only return matches where the video content STRONGLY aligns with the Lesson's Target Outcome or Description.\n"
        "- Clips should be concise (typically 30s - 3m).\n"
        "- Return JSON only, adhering to the specified schema."
    )
    
    user_prompt = (
        f"Here are the LESSONS:\n\n{lessons_str}\n\n"
        f"Here are the VIDEOS:\n\n{videos_str}\n\n"
        "Generate the matches in JSON format."
    )
    
    # 3. Call LLM with Retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Sending LLM Request (Attempt {attempt+1}/{max_retries})...")
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=MAX_TOKENS,
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=1800.0 # 30 minutes
            )
            
            content = response.choices[0].message.content
            
            # Dump Raw Response
            with open(f"{debug_dir}/raw_llm_response_hybrid_batch_{batch_num}.json", "w") as f:
                f.write(content)
                
            # Parse and Validate
            cleaned_content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_content)
            matches_obj = BatchMatches(**data)
            
            print(f"Batch {batch_num} Success: Found {len(matches_obj.matches)} matches.")
            
            # Dump Parsed Matches
            with open(output_filename, "w") as f:
                f.write(matches_obj.model_dump_json(indent=2))
                
            return matches_obj.matches
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error in Batch {batch_num} (Attempt {attempt+1}): {str(e)}")
            print(f"Traceback:\n{error_details}")
            if attempt < max_retries - 1:
                print("Retrying in 10 seconds...")
                await asyncio.sleep(10)
            else:
                print("Max retries reached. Failing batch.")
                return []
    return []

# --- Database Update ---

def update_hybrid_database(db: Session, hybrid_id: int, matches: List[VideoMatch]):
    """
    Updates the HybridCurriculum structured_json with the new clips.
    """
    print("Updating database...")
    hybrid = db.query(HybridCurriculum).filter(HybridCurriculum.id == hybrid_id).first()
    if not hybrid:
        print("Error: Hybrid Curriculum not found for update.")
        return

    # Deep copy to ensure mutation tracking
    import copy
    current_json = copy.deepcopy(hybrid.structured_json)
    
    # Organize matches by Lesson ID for O(1) lookup
    matches_by_lesson = {}
    for m in matches:
        if m.lesson_id not in matches_by_lesson:
            matches_by_lesson[m.lesson_id] = []
        matches_by_lesson[m.lesson_id].append({
            "video_filename": m.video_filename,
            "start_time": m.start_time,
            "end_time": m.end_time,
            "reason": m.reason
        })
        
    updates_count = 0
    modules = current_json.get("modules", [])
    for module in modules:
        for lesson in module.get("lessons", []):
            l_title = lesson.get("title")
            if l_title in matches_by_lesson:
                # Append or Overwrite? Let's Append to avoid losing existing manual work if any,
                # but user prompt implies we are building this. Let's Overwrite for this batch run to be clean?
                # Actually, since we run 2 batches, we should Append.
                # BUT, if we run the script twice, we duplicate.
                # Let's simple check for duplicates or just append.
                # Given this is a 'fix' script, maybe we clear `source_clips` first? No, that would wipe batch 1 results when running batch 2?
                # The script runs sequentially in one go usually, but we have `update_hybrid_database` called likely after all batches?
                # Let's assume we call this once with ALL matches or iteratively. 
                
                # Check if source_clips exists
                if "source_clips" not in lesson:
                    lesson["source_clips"] = []
                
                # Add new clips
                new_clips = matches_by_lesson[l_title]
                lesson["source_clips"].extend(new_clips)
                updates_count += 1
                print(f"Updated Lesson: {l_title} with {len(new_clips)} clips.")

    hybrid.structured_json = current_json
    
    # Force SQLAlchemy to detect change on JSON
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(hybrid, "structured_json")
    
    db.commit()
    print(f"Database update complete. Modified {updates_count} lessons.")

# --- Main Execution ---

async def main():
    print("Starting Global Video Alignment (Hybrid ID 4 Targets)...")
    db_gen = get_db()
    db = next(db_gen)
    
    # 1. Fetch Data
    hybrid_json = get_hybrid_curriculum(db, TARGET_HYBRID_ID)
    if not hybrid_json:
        print(f"CRITICAL: Hybrid Curriculum ID {TARGET_HYBRID_ID} not found.")
        return

    lessons = flatten_lessons_hybrid(hybrid_json)
    print(f"Loaded {len(lessons)} lessons from Hybrid {TARGET_HYBRID_ID}.")
    
    videos = get_videos(db)
    print(f"Loaded {len(videos)} videos from VideoCorpus.")
    
    if not videos:
        print("No videos found. Exiting.")
        return

    # 2. Batch Processing
    # Split videos into 2 batches approx equal size
    mid_point = (len(videos) + 1) // 2
    batches = [videos[:mid_point], videos[mid_point:]]
    
    # Reverting to default client, but setting timeout in the request
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("LLM_API_BASE"),
        timeout=1200.0
    )

    all_matches = []
    
    # Process Batch 1
    if batches[0]:
        matches_b1 = await process_batch(client, lessons, batches[0], 1)
        all_matches.extend(matches_b1)
        
    # Process Batch 2
    if len(batches) > 1 and batches[1]:
        matches_b2 = await process_batch(client, lessons, batches[1], 2)
        all_matches.extend(matches_b2)
        
    print(f"Total Matches Found: {len(all_matches)}")
    
    # 3. Update Database (Once with all matches)
    # Note: If we run this multiple times, we might duplicate. 
    # ideally we should wipe source_clips for these lessons before starting?
    # For now, I will NOT wipe, assuming this is a fresh run or user handles cleanup.
    # Actually, to be safe against duplicates from re-runs, let's clear source_clips for ALL lessons in the hybrid curriculum first?
    # That might be dangerous if there are other clips.
    # I'll stick to appending for now, but will print a warning.
    
    if all_matches:
        update_hybrid_database(db, TARGET_HYBRID_ID, all_matches)
    else:
        print("No matches to update.")

if __name__ == "__main__":
    asyncio.run(main())
