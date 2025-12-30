import sys
sys.path.append("/app")

import asyncio
from typing import List
from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services.llm import generate_structure_validated
from app.models.rich_content import GlobalVideoMatchResponse, VideoMatch, VideoReference, HybridLessonRichContent
from sqlalchemy.orm.attributes import flag_modified

COURSE_ID = 4
BJJ_KEYWORDS = ["bjj", "jiu", "grappling", "guard"]

# Updated prompt to strictly enforce Seconds format
SYSTEM_PROMPT = """
You are an expert Curriculum Architect for National Grid.
Your task is to analyze a batch of video transcripts and identify which specific lessons in the curriculum they belong to.

You have access to:
1. THE CURRICULUM: A list of all lessons in the course.
2. THE VIDEO LIBRARY: A batch of video transcripts.

For EACH video in the library:
1. Identify if it contains content highly relevant to ANY of the lessons.
2. If relevant, create a match.
3. EXTRACT START/END TIMES IN SECONDS (Float).
   - EXAMPLE: 90.5 (for 1m 30.5s)
   - DO NOT USE "HH:MM:SS" format.
4. FOR THE "lesson_id" FIELD: Use the EXACT Lesson Title from the provided curriculum list.

CRITICAL: Return a JSON object with a 'matches' list.
The objects MUST follow this structure EXACTLY:
{
  "matches": [
    {
      "lesson_id": "Exact Lesson Title Here",
      "video_filename": "exact_filename.mp4",
      "start_time": 120.5,
      "end_time": 180.0,
      "reason": "Explanation of relevance..."
    }
  ]
}
"""

async def process_batch(batch_name: str, video_batch: List[k_models.VideoCorpus], curriculum_context: str) -> List[VideoMatch]:
    if not video_batch:
        return []
    
    print(f"--- Processing {batch_name} ({len(video_batch)} videos) ---")
    
    video_context = ""
    for v in video_batch:
        txt = v.transcript_text or ""
        # Truncate very long transcripts to valid context window overlap if needed, 
        # but 8 videos should fit easily in 128k context if they aren't massive.
        # We'll truncate to 150k chars per video to be safe-ish? 
        # Actually with 8 videos, 100k chars each is 800k chars = too big using simple concat?
        # Videos are 20k-80k chars mostly. 8 * 50k = 400k chars. Might be tight for standard models, 
        # but Grok has large context.
        # Let's limit strictly to ensure success.
        limit = 100000 
        video_context += f"\n=== VIDEO: {v.filename} ===\n"
        video_context += f"Length: {len(txt)} \n"
        video_context += f"Transcript:\n{txt[:limit]}...\n"

    user_content = f"""
CURRICULUM STRUCTURE:
{curriculum_context}

VIDEO LIBRARY ({batch_name}):
{video_context}

TASK:
Find all relevant clips for the lessons.
Remember: Timestamps must be in SECONDS (e.g. 150.0).
"""

    try:
        response = await generate_structure_validated(
            system_prompt=SYSTEM_PROMPT,
            user_content=user_content,
            model_class=GlobalVideoMatchResponse,
            model="x-ai/grok-4.1-fast",
            max_retries=2
        )
        print(f" > {batch_name} Result: Found {len(response.matches)} matches.")
        return response.matches
    except Exception as e:
        print(f" > {batch_name} Failed: {e}")
        return []

async def main():
    db = SessionLocal()
    try:
        # 1. Fetch Curriculum
        print("Fetching Curriculum...")
        course = db.query(k_models.HybridCurriculum).get(COURSE_ID)
        if not course:
            print("Course 4 not found.")
            return

        curriculum_context = ""
        struct = course.structured_json
        for m in struct.get("modules", []):
            curriculum_context += f"\nMODULE: {m['title']}\n"
            for l in m.get("lessons", []):
                l_title = l.get("title")
                curriculum_context += f" - Lesson: '{l_title}'\n"

        # 2. Fetch & Filter Videos (Strict Utility List)
        all_videos = db.query(k_models.VideoCorpus).all()
        utility_videos = [v for v in all_videos if not any(k in v.filename.lower() for k in BJJ_KEYWORDS)]
        
        print(f"Target Utility Videos: {len(utility_videos)}")
        for v in utility_videos:
            print(f" - {v.filename}")

        # 3. Split into 2 Batches
        mid_index = len(utility_videos) // 2
        batch_a = utility_videos[:mid_index]
        batch_b = utility_videos[mid_index:]
        
        # 4. Execute
        matches_a = await process_batch("Batch A", batch_a, curriculum_context)
        matches_b = await process_batch("Batch B", batch_b, curriculum_context)
        
        all_matches = matches_a + matches_b
        print(f"Total Matches: {len(all_matches)}")

        # 5. Update DB
        print("Updating Database...")
        matches_by_lesson = {}
        for m in all_matches:
            if m.lesson_id not in matches_by_lesson:
                matches_by_lesson[m.lesson_id] = []
            matches_by_lesson[m.lesson_id].append(m)
            
        update_count = 0
        for mod in struct["modules"]:
            for lesson in mod["lessons"]:
                l_title = lesson.get("title")
                # Also check for near matches if exact match fails? 
                # For now assume LLM extracts exact title or we do fuzzy match later.
                # Actually, let's try exact first.
                
                # Check exact match
                lesson_matches = matches_by_lesson.get(l_title, [])
                
                # If LLM returned slightly different title, we might miss it.
                # But let's trust exact for now.
                
                if lesson_matches:
                    if "source_clips" not in lesson:
                         lesson["source_clips"] = []
                    
                    # Deduplicate
                    existing_sigs = set((c["video_filename"], c["start_time"]) for c in lesson.get("source_clips", []))
                    
                    for m in lesson_matches:
                        sig = (m.video_filename, m.start_time)
                        if sig not in existing_sigs:
                            lesson["source_clips"].append({
                                "video_filename": m.video_filename,
                                "start_time": m.start_time,
                                "end_time": m.end_time,
                                "reason": m.reason
                            })
                            update_count += 1
                            print(f" + Added clip to '{l_title}'")

        course.structured_json = struct
        flag_modified(course, "structured_json")
        db.commit()
        print(f"Done. Persisted {update_count} new clips.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
