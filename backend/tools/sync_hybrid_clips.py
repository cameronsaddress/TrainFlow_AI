import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models.knowledge import TrainingCurriculum, HybridCurriculum

def main():
    db = SessionLocal()
    try:
        # 1. Get Master Curriculum (Source of Truth)
        master = db.query(TrainingCurriculum).order_by(TrainingCurriculum.created_at.desc()).first()
        if not master:
            print("❌ No TrainingCurriculum found.")
            return

        # 2. Get Target Hybrid Curriculum
        target_id = 4
        hybrid = db.query(HybridCurriculum).filter(HybridCurriculum.id == target_id).first()
        if not hybrid:
            print(f"❌ HybridCurriculum {target_id} not found.")
            return

        print(f"🔄 Syncing clips from TrainingCurriculum (ID: {master.id}) to HybridCurriculum {target_id}...")

        # 3. Build Source Map (Title -> Clips)
        # Using Title as key since IDs were unreliable/None
        clip_map = {}
        source_count = 0
        
        for m in master.structured_json.get("modules", []):
            for l in m.get("lessons", []):
                title = l.get("title")
                clips = l.get("source_clips", [])
                if title and clips:
                    clip_map[title] = clips
                    source_count += len(clips)
        
        print(f"   📍 Found {source_count} clips across {len(clip_map)} lessons in Master.")

        # 4. Update Hybrid
        hybrid_data = hybrid.structured_json
        updates_made = 0
        
        for m in hybrid_data.get("modules", []):
            for l in m.get("lessons", []):
                title = l.get("title")
                if title in clip_map:
                    # Overwrite/Set clips
                    # We could merge, but usually we want the latest "truth"
                    # Let's check if they are actually different to avoid unnecessary writes
                    current_clips = l.get("source_clips", [])
                    new_clips = clip_map[title]
                    
                    # Simple equality check might fail if order differs, but good enough for now
                    # Or just overwrite to be safe.
                    l["source_clips"] = new_clips
                    updates_made += len(new_clips)
                    print(f"      ✅ Updated {title} with {len(new_clips)} clips.")

        # 5. Commit
        if updates_made > 0:
            hybrid.structured_json = hybrid_data
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(hybrid, "structured_json")
            db.commit()
            print(f"   💾 Successfully synced {updates_made} clips to HybridCurriculum {target_id}.")
        else:
            print("   ✨ No updates needed (counts matched or no matches found).")

    finally:
        db.close()

if __name__ == "__main__":
    main()
