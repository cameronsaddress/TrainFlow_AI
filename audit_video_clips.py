
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
# import model_loader # Helper to load models if needed, or just raw SQL for speed

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app.db import Base, get_db
from app.models import knowledge as k_models

# Setup DB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname") # Adjust if needed, or rely on env
# Actually, better to just use the existing db setup
from app.db import SessionLocal

def audit_clips():
    db = SessionLocal()
    try:
        # 1. Get all available videos
        videos = db.query(k_models.VideoCorpus).all()
        video_map = {v.filename: v for v in videos}
        print(f"Found {len(videos)} videos in VideoCorpus table.")
        for v in videos:
            print(f" - {v.filename} (Path: {v.file_path})")

        # 2. Get the Hybrid Curriculum
        # Assuming ID 4 as per context, or get the latest
        course = db.query(k_models.HybridCurriculum).order_by(k_models.HybridCurriculum.id.desc()).first()
        if not course:
            print("No HybridCurriculum found.")
            return

        print(f"\nAuditing Course: {course.title} (ID: {course.id})")
        
        if not course.structured_json:
            print("No structured_json found.")
            return

        modules = course.structured_json.get("modules", [])
        total_clips = 0
        valid_clips = 0
        broken_clips = 0

        for m_idx, mod in enumerate(modules):
            lessons = mod.get("lessons", [])
            for l_idx, lesson in enumerate(lessons):
                clips = lesson.get("source_clips", [])
                for c_idx, clip in enumerate(clips):
                    total_clips += 1
                    video_filename = clip.get("video_filename")
                    start = clip.get("start_time")
                    end = clip.get("end_time")

                    issues = []
                    
                    # Check 1: Filename
                    if not video_filename:
                        issues.append("Missing video_filename")
                    elif video_filename not in video_map:
                        # Try fuzzy check logic from router
                        found = False
                        # Simple check
                        if video_filename.replace(" ", "_") in video_map: found = True
                        if video_filename.replace("_", " ") in video_map: found = True
                        
                        if not found:
                             issues.append(f"Video file not found in DB: '{video_filename}'")
                    
                    # Check 2: Times
                    if start is None or end is None:
                        issues.append(f"Missing start/end times: {start}-{end}")
                    else:
                        try:
                            s = float(start)
                            e = float(end)
                            if s >= e and e != -1: # -1 might mean end?
                                issues.append(f"Invalid duration: {s} -> {e}")
                        except ValueError:
                             issues.append(f"Non-numeric times: {start}-{end}")

                    if issues:
                        broken_clips += 1
                        print(f"❌ broken clip in Mod {m_idx} Les {l_idx} '{lesson.get('title')}': {issues}")
                        print(f"   Context: {clip}")
                    else:
                        valid_clips += 1
                        # print(f"✅ Valid clip: {video_filename} ({start}-{end})")
            
        print(f"\nAudit Complete.")
        print(f"Total Clips: {total_clips}")
        print(f"Valid Clips: {valid_clips}")
        print(f"Broken Clips: {broken_clips}")
        
        # New Stats
        zero_start = 0
        non_zero_start = 0
        
        for m_idx, mod in enumerate(modules):
            for l_idx, lesson in enumerate(mod.get("lessons", [])):
                for clip in lesson.get("source_clips", []):
                    try:
                        s = float(clip.get("start_time", 0))
                        if s == 0.0:
                            zero_start += 1
                        else:
                            non_zero_start += 1
                    except:
                        pass
                        
        print(f"\nTime Analysis:")
        print(f"Starts at 0.0s: {zero_start}")
        print(f"Starts > 0.0s:  {non_zero_start}")
        if non_zero_start > 0:
             print("Conclusion: NOT all clips start at 0.")
        else:
             print("Conclusion: YES, all clips start at 0.")

    finally:
        db.close()

if __name__ == "__main__":
    audit_clips()
