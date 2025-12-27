import requests
import json
import sys

API_URL = "http://localhost:2027/api/curriculum"

def inspect_latest_curriculum():
    # 1. Fetch all plans to get latest ID
    try:
        # Assuming there's an endpoint to list all, otherwise we need to guess or use the DB
        # If no list endpoint, we'll try to GET /api/curriculum/plans/latest if it exists
        # Or we can iterate IDs.
        
        # Let's try to list first. Based on router, it might be /api/curriculum/plans
        resp = requests.get(f"{API_URL}/plans")
        if resp.status_code != 200:
            print(f"Failed to list plans: {resp.status_code} {resp.text}")
            return
            
        plans = resp.json()
        if not plans:
            print("No plans found.")
            return

        # Sort by ID descending (assuming larger ID is newer)
        latest = sorted(plans, key=lambda x: x['id'], reverse=True)[0]
        curr_id = latest['id']
        print(f"--- Inspecting Curriculum ID: {curr_id} ---")
        
        # 2. Fetch details
        resp = requests.get(f"{API_URL}/plans/{curr_id}")
        data = resp.json()
        
        # 3. Inspect specific module
        structure = data.get("structured_json", {})
        modules = structure.get("modules", [])
        
        target_video_key = "Work Order Training - Day 1 Part1"
        found = False

        for m_idx, m in enumerate(modules):
            title = m.get("title", "")
            sources = m.get("recommended_source_videos", [])
            
            # Heuristic match - strictly for Module 1 or exact video filename match
            # "Module 1:" matches Module 1 but not Module 12
            is_target = any(target_video_key.lower() in s.lower() for s in sources) or "module 1:" in title.lower()
            
            if is_target:
                found = True
                print(f"\n[MODULE {m_idx+1}] {title}")
                print(f"  ID: {m.get('id')}")
                print(f"  Sources: {sources}")
                print(f"  Lesson Count: {len(m.get('lessons', []))}")
                
                for l_idx, l in enumerate(m.get('lessons', [])):
                    print(f"  [Lesson {l_idx+1}] {l.get('title')}")
                    clips = l.get("source_clips", [])
                    print(f"    Clips: {len(clips)}")
                    for c in clips:
                        fname = c.get("video_filename")
                        try:
                            start = float(c.get("start_time", 0))
                            end = float(c.get("end_time", 0))
                            dur = end - start
                        except (ValueError, TypeError):
                            start, end, dur = 0, 0, 0
                            
                        print(f"      - {fname}")
                        print(f"        Start: {start} | End: {end} | Dur: {dur}s ({dur/60:.2f}m)")

        if not found:
            print("Target module not found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_latest_curriculum()
