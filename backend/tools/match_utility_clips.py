import os
import sys
import json
import asyncio
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append("/app")

from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import AsyncOpenAI

# DB Imports
from app.db import SessionLocal
from app.models.knowledge import VideoCorpus, HybridCurriculum

# Load environment variables
load_dotenv()

# --- Configuration ---
BATCH_SIZE_VIDEOS = 4 
MODEL_NAME = "x-ai/grok-4.1-fast"
MAX_TOKENS = 30000
TARGET_HYBRID_ID = 4

# --- Pydantic Models for LLM Output ---
class VideoMatch(BaseModel):
    lesson_title: str = Field(description="The exact TITLE of the lesson this clip belongs to")
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

def get_utility_videos(db: Session) -> List[Dict]:
    """
    Fetches videos from VideoCorpus that are categorized as 'utility'.
    Returns a list of dicts: {filename, duration, transcript}
    """
    # We use raw SQL for JSONB querying or just filter in python if list is small
    # List is small (21 total, 16 utility). Python filter is fine and safer/easier.
    videos = db.query(VideoCorpus).all()
    video_list = []
    
    print(f"Scanning {len(videos)} videos for 'utility' category...")
    
    for v in videos:
        # Check Category
        is_utility = False
        if v.metadata_json:
            # metadata_json might be dict or string depending on driver/model usage, usually dict in ORM
            meta = v.metadata_json
            if isinstance(meta, dict) and meta.get("category") == "utility":
                is_utility = True
        
        # Fallback: Check hardcoded specific filenames if metadata fails (just in case)
        if not is_utility:
             # Basic check if NOT bjj
             if "jiu" not in v.filename.lower() and "bjj" not in v.filename.lower():
                 # print(f"Heuristic Match for Utility: {v.filename}")
                 # Actually, let's trust the DB update we just did.
                 pass

        if not is_utility:
            continue

        # Get Transcript
        transcript_content = ""
        if v.transcript_json:
            try:
                segments = v.transcript_json
                if isinstance(segments, dict) and "timeline" in segments:
                     # New structure mentioned in README: {timeline: [{word, start, end}]}
                     # Wait, user said "transcript_json column... contains a transcript_json key... which contains a timeline key"
                     # Let's check what we see. 
                     # Actually user said: "transcript_json contains a timeline key"
                     # If it's word-level, recreating full sentences is hard without grouping.
                     # Let's hope there is a 'text' field or we reconstruct.
                     # Reconstructing from words:
                     timeline = segments.get("timeline", [])
                     words = [t.get("word", "") for t in timeline if "word" in t]
                     transcript_content = " ".join(words)
                elif isinstance(segments, list):
                     # Segment list format
                     lines = []
                     for seg in segments:
                         start = seg.get('start', 0)
                         text_seg = seg.get('text', '').strip()
                         lines.append(f"[{int(start)}s] {text_seg}")
                     transcript_content = "\n".join(lines)
            except Exception as e:
                print(f"Error parsing JSON for {v.filename}: {e}")
        
        if not transcript_content and v.transcript_text:
             transcript_content = v.transcript_text

        if not transcript_content:
            print(f"Skipping {v.filename}: No transcript content.")
            continue
            
        # Truncate if massive (safety)
        if len(transcript_content) > 150000:
             transcript_content = transcript_content[:150000] + "...(truncated)"

        video_list.append({
            "filename": v.filename,
            "transcript": transcript_content
        })
        
    print(f"Found {len(video_list)} Utility videos with transcripts.")
    return video_list

def extract_lessons(structured_json: Dict) -> List[Dict]:
    """
    Extracts lessons with Title, Target Outcome, and Summary.
    """
    lessons = []
    modules = structured_json.get("modules", [])
    for module in modules:
        for lesson in module.get("lessons", []):
            title = lesson.get("title", "Unknown")
            outcome = lesson.get("learning_objective", "None")
            
            # Summary from content blocks
            summary = ""
            for block in lesson.get("content_blocks", []):
                if block.get("type") == "text":
                    summary = block.get("content", "")[:300] # Cap summary
                    break
            
            lessons.append({
                "title": title,
                "outcome": outcome,
                "summary": summary
            })
    return lessons

# --- LLM Processing ---

async def process_batch(client: AsyncOpenAI, lessons: List[Dict], videos: List[Dict], batch_num: int):
    print(f"--- Processing Batch {batch_num} ({len(videos)} videos) ---")
    
    # Context Construction
    lessons_str = ""
    for l in lessons:
        lessons_str += f"""
LESSON: {l['title']}
OUTCOME: {l['outcome']}
SUMMARY: {l['summary']}
---"""

    videos_str = ""
    for v in videos:
        videos_str += f"""
VIDEO: {v['filename']}
TRANSCRIPT:
{v['transcript']}
---"""

    system_prompt = (
        "You are an Expert Training Curriculum Curator. Your goal is to find video segments that help trainees learn faster.\n"
        "Input: List of LESSONS (Title, Outcome, Summary) and VIDEOS (Timestamped Transcripts).\n"
        "Task: Return a JSON list of matches.\n"
        "GUIDELINES:\n"
        "1. VISUALIZATION IS KEY: If a video shows or discusses the concept, MATCH IT. It doesn't need to be a perfect definition, just helpful context.\n"
        "2. EXAMPLES OVER THEORY: Look for practical demonstrations, field work, or examples that clarify the lesson.\n"
        "3. TIMESTAMP ACCURACY: You MUST provide the specific start and end time from the transcript (e.g., [45s] to [120s]).\n"
        "4. AVOID THE '0s' TRAP: Do not lazily default to 0s. Find the ACTUAL moment the relevant content starts.\n"
        "5. KEEP IT SNAPPY: Clips should be 30s-3 mins. Enough to learn, short enough to keep attention.\n"
        "Output JSON Schema: [{ 'lesson_title': str, 'video_filename': str, 'start_time': float, 'end_time': float, 'reason': str }]"
    )
    
    user_prompt = f"We helping trainees learn faster. If any video content pertains to these lessons, give us the specific clip.\n\nLESSONS:\n{lessons_str}\n\nVIDEOS:\n{videos_str}\n\nGenerate helpful video matches."
    
    print(f"Sending request to {MODEL_NAME} (Curator Mode)...")
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.3, # Slight creativity allowed for matching
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        clean_json = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        # Validate/Parse
        if "matches" in data:
            matches = [VideoMatch(**m) for m in data["matches"]]
        elif isinstance(data, list):
            matches = [VideoMatch(**m) for m in data]
        else:
            matches = []
            
        print(f"Batch {batch_num} returned {len(matches)} matches.")
        return matches
        
    except Exception as e:
        print(f"Error in Batch {batch_num}: {e}")
        return []

# --- Main ---

async def main():
    print("Starting Utility Video Matcher...")
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # 1. Fetch
        hybrid_json = get_hybrid_curriculum(db, TARGET_HYBRID_ID)
        if not hybrid_json:
            print("Curriculum not found.")
            return

        lessons = extract_lessons(hybrid_json)
        print(f"Loaded {len(lessons)} lessons.")
        
        videos = get_utility_videos(db)
        if not videos:
            print("No utility videos found.")
            return

        # 1.5 CLEAR EXISTING CLIPS (Purge Bad Data)
        print("Purging existing source_clips for Course 4...")
        # Reload to ensure we have the latest
        hybrid = db.query(HybridCurriculum).filter(HybridCurriculum.id == TARGET_HYBRID_ID).first()
        if hybrid and hybrid.structured_json:
            j = hybrid.structured_json
            cleared_count = 0
            for m in j.get("modules", []):
                for l in m.get("lessons", []):
                    if "source_clips" in l and l["source_clips"]:
                        l["source_clips"] = []
                        cleared_count += 1
            
            hybrid.structured_json = j
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(hybrid, "structured_json")
            db.commit()
            print(f"Cleared source_clips from {cleared_count} lessons.")

        # 2. Batching
        client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_API_BASE"),
            timeout=1200.0
        )
        
        # Split videos into chunks of BATCH_SIZE_VIDEOS
        video_batches = [videos[i:i + BATCH_SIZE_VIDEOS] for i in range(0, len(videos), BATCH_SIZE_VIDEOS)]
        print(f"Created {len(video_batches)} batches.")
        
        all_matches = []
        for i, batch in enumerate(video_batches):
            matches = await process_batch(client, lessons, batch, i+1)
            all_matches.extend(matches)

        print(f"Total Matches: {len(all_matches)}")
        
        # 3. Update DB
        if all_matches:
            print("Updating database...")
            # Group by lesson title
            matches_map = {}
            for m in all_matches:
                if m.lesson_title not in matches_map:
                    matches_map[m.lesson_title] = []
                matches_map[m.lesson_title].append({
                    "video_filename": m.video_filename,
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                    "reason": m.reason
                })
            
            # Apply updates
            update_count = 0
            # Reload fresh JSON just in case
            course_obj = db.query(HybridCurriculum).filter(HybridCurriculum.id == TARGET_HYBRID_ID).first()
            j = course_obj.structured_json
            
            for m in j.get("modules", []):
                for l in m.get("lessons", []):
                    title = l.get("title")
                    if title in matches_map:
                        if "source_clips" not in l:
                            l["source_clips"] = []
                        
                        # Avoid duplicates: check if same filename+start exists
                        existing_sig = {f"{c['video_filename']}_{c['start_time']}" for c in l["source_clips"]}
                        
                        for new_clip in matches_map[title]:
                            sig = f"{new_clip['video_filename']}_{new_clip['start_time']}"
                            if sig not in existing_sig:
                                l["source_clips"].append(new_clip)
                                update_count += 1
            
            # Save
            course_obj.structured_json = j
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(course_obj, "structured_json")
            db.commit()
            print(f"Saved {update_count} new clips to database.")
        
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
