import sqlite3
import json
import sys

DB_PATH = "/home/canderson/TrainFlow_AI/backend/trainflow.db"

def inspect_clips():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get the latest curriculum
    cursor.execute("SELECT id, structured_json FROM training_curricula ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    
    if not row:
        print("No curriculum found.")
        return

    curr_id, json_str = row
    data = json.loads(json_str)

    print(f"--- Inspecting Curriculum ID: {curr_id} ---")

    modules = data.get("modules", [])
    
    # Filter for "Day 1 Part 1" or Unit 1 related content
    # The user mentioned "Module 1" and "Work Order Training Day 1 Part 1"
    
    # We'll just look for the first module or matches
    target_video_key = "Work Order Training - Day 1 Part1"

    for m in modules:
        # Check source videos
        sources = m.get("recommended_source_videos", [])
        is_target = any(target_video_key in s for s in sources)
        
        # Also check title just in case
        if "Module 1" in m.get("title", "") or is_target:
            print(f"\nMODULE: {m.get('title')} (ID: {m.get('id')})")
            print(f"Sources: {sources}")
            
            for l in m.get("lessons", []):
                print(f"  LESSON: {l.get('title')}")
                for clip in l.get("source_clips", []):
                    start = clip.get("start_time")
                    end = clip.get("end_time")
                    fname = clip.get("video_filename")
                    duration_sec = (end or 0) - (start or 0)
                    duration_min = duration_sec / 60.0
                    print(f"    CLIP: {fname}")
                    print(f"      Start: {start} | End: {end} | Dur: {duration_min:.2f}m")

if __name__ == "__main__":
    inspect_clips()
