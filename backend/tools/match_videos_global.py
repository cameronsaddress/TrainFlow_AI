import sys
import os
import json
import asyncio
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models.knowledge import VideoCorpus, TrainingCurriculum
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

# Load env vars
load_dotenv()

from openai import AsyncOpenAI

# --- Pydantic Models for LLM Response ---
class VideoMatch(BaseModel):
    lesson_id: str
    video_filename: str
    start_time: float
    end_time: float
    reason: str

class MatchResponse(BaseModel):
    matches: List[VideoMatch]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def format_transcript(video: VideoCorpus) -> str:
    """
    Format the transcript from VideoCorpus into a string with timestamps.
    """
    try:
        if not video.transcript_json:
            return "(No Transcript Available)"
            
        # Handle different potential JSON structures
        # 1. List of segments: [{"start": 0, "end": 10, "text": "..."}]
        # 2. Object with segments: {"segments": [...]}
        # 3. Just text? No we need timestamps.
        segments = []
        if isinstance(video.transcript_json, list):
            segments = video.transcript_json
        elif isinstance(video.transcript_json, dict):
            segments = video.transcript_json.get("segments", [])
            
        if not segments:
            # Fallback debug
            return f"(Empty Transcript JSON: {str(video.transcript_json)[:200]})"

        formatted = []
        for seq, seg in enumerate(segments):
            # Sample every X segments if needed, but Grok has 2M context.
            # We will provide FULL transcripts as user requested.
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            text = seg.get("text", "").strip()
            formatted.append(f"[{start:.1f}-{end:.1f}] {text}")
            
        return "\n".join(formatted)
        
    except Exception as e:
        return f"(Error formatting transcript: {str(e)})"

def flatten_lessons(curriculum_json: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """
    Flattens the curriculum into a text format for the LLM and a map for lookup.
    """
    lesson_map = {}
    lines = []
    
    modules = curriculum_json.get("modules", [])
    for m in modules:
        m_title = m.get("title", "Untitled Module")
        for l in m.get("lessons", []):
            # Use TITLE as ID if ID is missing
            l_id = l.get("id") or l.get("title")
            l_title = l.get("title", "Untitled Lesson")
            
            # Use voiceover_script or learning_objective if content is missing
            raw_content = l.get("content", "")
            if not raw_content:
                raw_content = l.get("voiceover_script", "")
            if not raw_content:
                 raw_content = str(l.get("learning_objective", ""))
                 
            # Truncate content to avoid insane token usage, but keep enough
            l_content = str(raw_content)[:5000] 
            
            lesson_map[l_id] = l
            
            lines.append(f"LESSON_ID: {l_id}")
            lines.append(f"MODULE: {m_title}")
            lines.append(f"TITLE: {l_title}")
            lines.append(f"CONTENT_SUMMARY: {l_content}")
            lines.append("---")
            
    return "\n".join(lines), lesson_map

def update_database(db: Session, matches: List[Dict], curriculum: TrainingCurriculum, lesson_map: Dict):
    """
    Updates the TrainingCurriculum structured_json with the matched clips.
    """
    print(f"   💾 updating {len(matches)} matches in DB...")
    
    # Reload curriculum to ensure freshness
    db.refresh(curriculum)
    data = curriculum.structured_json
    modules = data.get("modules", [])
    
    param_updates = 0
    
    for match in matches:
        l_id = match.get("lesson_id")
        fname = match.get("video_filename")
        start = match.get("start_time")
        end = match.get("end_time")
        reason = match.get("reason")
        
        # Validate logic
        if end <= start:
            print(f"      ⚠️ Skipping invalid range {start}-{end} for {l_id}")
            continue
            
        # Find lesson in JSON
        found = False
        for m in modules:
            for l in m.get("lessons", []):
                # Match by ID or Title
                current_id = l.get("id") or l.get("title")
                if current_id == l_id:
                    # Update Source Clips
                    new_clip = {
                        "video_filename": fname,
                        "start_time": start,
                        "end_time": end,
                        "title": reason # Using reason as title/caption
                    }
                    
                    # Check if already exists basically
                    exists = False
                    if "source_clips" not in l:
                        l["source_clips"] = []
                        
                    for existing in l["source_clips"]:
                        if existing.get("video_filename") == fname and abs(existing.get("start_time", 0) - start) < 1.0:
                            exists = True
                            break
                    
                    if not exists:
                        l["source_clips"].append(new_clip)
                        param_updates += 1
                        print(f"      ✅ Matched: {l.get('title')} -> {fname} ({start}-{end})")
                    else:
                        print(f"      ℹ️ Clip already exists for {l.get('title')}")
                        
                    found = True
                    break
            if found: break
            
    if param_updates > 0:
        curriculum.structured_json = data
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(curriculum, "structured_json")
        db.commit()
        print(f"   💾 Committed {param_updates} new clips to database.")
    else:
        print("   ✨ No new database updates needed.")

def main():
    print("🚀 Starting Global Video Alignment (2-Batch Strategy)...")
    
    db = SessionLocal()
    try:
        # 1. Fetch Resources
        # Use VideoCorpus which we confirmed has the transcripts
        all_videos = db.query(VideoCorpus).filter(VideoCorpus.transcript_json.isnot(None)).all()
        print(f"📹 Found {len(all_videos)} videos with transcripts in VideoCorpus.")
        
        # Get latest curriculum
        curriculum = db.query(TrainingCurriculum).order_by(TrainingCurriculum.created_at.desc()).first()
        if not curriculum:
            print("❌ No curriculum found.")
            return

        lessons_text, lesson_map = flatten_lessons(curriculum.structured_json)
        print(f"📚 Loaded {len(lesson_map)} lessons.")

        # 2. Batch Strategy
        # Split videos into 2 chunks
        total_videos = len(all_videos)
        if total_videos == 0:
            print("❌ No videos to match.")
            return

        mid_point = (total_videos + 1) // 2
        batches = [
            all_videos[:mid_point],
            all_videos[mid_point:]
        ]
        
        print(f"📦 Split into {len(batches)} batches (Batch 1: {len(batches[0])}, Batch 2: {len(batches[1])})")

        # 3. Process Batches
        total_matches = 0
        
        for i, video_batch in enumerate(batches):
            batch_num = i + 1
            print(f"\n⚡ Processing Batch {batch_num}...")
            
            # Prepare Video Context
            videos_context = []
            for v in video_batch:
                videos_context.append(f"VIDEO_ID: {v.filename}\nTRANSCRIPT:\n{format_transcript(v)}\n\n---")
            
            full_video_text = "\n".join(videos_context)
            
            # Dump Inputs for Debugging
            dump_dir = "/app/dumps"
            os.makedirs(dump_dir, exist_ok=True)
            
            with open(f"{dump_dir}/debug_transcripts_batch_{batch_num}.txt", "w") as f:
                f.write(full_video_text)
            
            with open(f"{dump_dir}/debug_lessons_batch_{batch_num}.txt", "w") as f:
                f.write(lessons_text)

            # Construct Prompt
            system_prompt = (
                "You are an expert video editor and curriculum designer. "
                "Your task is to find EXACT video clips that match specific lessons.\n"
                "You will be given a list of Lessons and a list of Video Transcripts with timestamps.\n"
                "Return a JSON object with a list of 'matches'. "
                "Each match must include:\n"
                "- lesson_id: The exact ID of the lesson (as provided in LESSON_ID)\n"
                "- video_filename: The exact filename of the video\n"
                "- start_time: float (in seconds)\n"
                "- end_time: float (in seconds)\n"
                "- reason: A very short justification\n\n"
                "RULES:\n"
                "1. Only match if the content is highly relevant.\n"
                "2. Clip duration should be between 30 and 180 seconds.\n"
                "3. Use the timestamps provided in the transcript.\n"
            )

            print(f"   🤖 Sending request to Grok... (Videos: {len(video_batch)}, Lessons: {len(lesson_map)})")
            
            try:
                # Synchronous call wrapper for async client
                async def run_llm():
                    client = AsyncOpenAI(
                        api_key=os.getenv("OPENAI_API_KEY"),
                        base_url=os.getenv("LLM_API_BASE")
                    )
                    
                    response = await client.chat.completions.create(
                        model="x-ai/grok-4.1-fast",  # Using the specified model
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"LESSONS:\n{lessons_text}\n\nVIDEOS:\n{full_video_text}"}
                        ],
                        response_format={"type": "json_object"},
                        max_completion_tokens=4096,
                        temperature=0.1
                    )
                    return response.choices[0].message.content

                raw_response = asyncio.run(run_llm())
                
                # Dump Response
                with open(f"{dump_dir}/video_matches_batch_{batch_num}.json", "w") as f:
                    f.write(raw_response)
                
                # Parse & Validate
                try:
                    parsed = json.loads(raw_response)
                    matches = parsed.get("matches", [])
                    print(f"   ✅ Batch {batch_num} returned {len(matches)} matches.")
                except json.JSONDecodeError:
                    print(f"   ❌ Batch {batch_num} returned Invalid JSON.")
                    matches = []
                
                # Update DB
                if matches:
                    update_database(db, matches, curriculum, lesson_map)
                    total_matches += len(matches)

            except Exception as e:
                print(f"   ❌ Error in Batch {batch_num}: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n🎉 Done! Total matches found: {total_matches}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
