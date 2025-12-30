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

SYSTEM_PROMPT = """
You are an expert Curriculum Architect for National Grid.
Your task is to analyze a batch of video transcripts and identify which specific lessons in the curriculum they belong to.

You have access to:
1. THE CURRICULUM: A list of all lessons in the course, organized by ID and Title.
2. THE VIDEO LIBRARY: A batch of video transcripts.

For EACH video in the library:
1. specific snippets (start/end times) that are highly relevant to a specific lesson.
2. If a video is relevant, you MUST create a match.
3. Be precise with start/end times.
4. A single video might contain clips for multiple different lessons.
5. A single lesson might get clips from multiple videos.

CRITICAL: Return a JSON object with a 'matches' list.
"""

async def process_batch(batch_name: str, video_batch: List[k_models.VideoCorpus], curriculum_context: str) -> List[VideoMatch]:
    if not video_batch:
        return []
    
    print(f"--- Processing {batch_name} ({len(video_batch)} videos) ---")
    
    # Build Video Context
    video_context = ""
    for v in video_batch:
        txt = v.transcript_text or ""
        video_context += f"\n=== VIDEO: {v.filename} ===\n"
        video_context += f"Length: {len(txt)} chars\n"
        video_context += f"Transcript:\n{txt[:150000]}...\n(Truncated if too long)\n"

    user_content = f"""
CURRICULUM STRUCTURE:
{curriculum_context}

VIDEO LIBRARY ({batch_name}):
{video_context}

TASK:
Find all relevant clips for the lessons in the curriculum.
Return a list of `VideoMatch` objects.
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
        # 1. Fetch Curriculum & Build Context
        print("Fetching Curriculum...")
        course = db.query(k_models.HybridCurriculum).get(COURSE_ID)
        if not course:
            print("Course not found!")
            return

        curriculum_map = {} # ID -> Lesson Object Pointer (for faster updates later? No, easier to just traverse)
        curriculum_context = ""
        
        # We need a way to map ID back to the JSON structure location, or just flattened list
        # We'll use a flattened context for the LLM
        
        struct = course.structured_json
        for m in struct.get("modules", []):
            curriculum_context += f"\nMODULE: {m['title']}\n"
            for l in m.get("lessons", []):
                l_id = l.get("id") # Assuming we have stable IDs, or we use Title as ID
                # If no ID, use title
                l_title = l.get("title")
                curriculum_context += f" - Lesson: '{l_title}' (ID: {l_title})\n" 
                # Note: Using Title as ID for matching since the text is what matters

        print(f"Curriculum Context Length: {len(curriculum_context)} chars")

        # 2. Fetch & Filter Videos
        print("Fetching and Filtering Videos...")
        all_videos = db.query(k_models.VideoCorpus).all()
        utility_videos = []
        
        print("Excluded Videos (BJJ):")
        for v in all_videos:
            is_bjj = any(k in v.filename.lower() for k in BJJ_KEYWORDS)
            if is_bjj:
                print(f" - {v.filename}")
            else:
                utility_videos.append(v)
        
        print(f"Target Utility Videos: {len(utility_videos)}")

        # 3. Split into 2 Batches
        mid_index = len(utility_videos) // 2
        batch_a = utility_videos[:mid_index]
        batch_b = utility_videos[mid_index:]
        
        # 4. Execute 2-Pass Matching
        matches_a = await process_batch("Batch A", batch_a, curriculum_context)
        matches_b = await process_batch("Batch B", batch_b, curriculum_context)
        
        all_matches = matches_a + matches_b
        print(f"Total Matches Found: {len(all_matches)}")

        # 5. Connect and Update Database
        print("Updating Database...")
        updates_count = 0
        
        # Group matches by Lesson Title (our ID)
        matches_by_lesson = {}
        for m in all_matches:
            if m.lesson_id not in matches_by_lesson:
                matches_by_lesson[m.lesson_id] = []
            matches_by_lesson[m.lesson_id].append(m)
            
        # Iterate curriculum and inject
        for mod in struct["modules"]:
            for lesson in mod["lessons"]:
                l_title = lesson.get("title")
                if l_title in matches_by_lesson:
                    new_clips = matches_by_lesson[l_title]
                    
                    # Convert to VideoReference (schema difference?)
                    # VideoMatch has lesson_id, VideoReference does not.
                    refs = []
                    for m in new_clips:
                        refs.append({
                            "video_filename": m.video_filename,
                            "start_time": m.start_time,
                            "end_time": m.end_time,
                            "reason": m.reason
                        })
                    
                    # Merge or Overwrite? Overwrite for now as this is a "Global Reset"
                    if "source_clips" not in lesson:
                         lesson["source_clips"] = []
                    
                    # Append new clips, avoiding duplicates if strictly identical
                    # checking filename + start_time
                    existing_sigs = set((c["video_filename"], c["start_time"]) for c in lesson.get("source_clips", []))
                    
                    for r in refs:
                        sig = (r["video_filename"], r["start_time"])
                        if sig not in existing_sigs:
                            lesson["source_clips"].append(r)
                            updates_count += 1
                            print(f" + Added clip to '{l_title}': {r['video_filename']} ({r['start_time']}s)")

        course.structured_json = struct
        flag_modified(course, "structured_json")
        db.commit()
        print(f"Done. Persisted {updates_count} new clips.")

    except Exception as e:
        print(f"Global Match Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
