import sys
import os
import json

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models

def audit_video_content():
    db = SessionLocal()
    try:
        videos = db.query(k_models.VideoCorpus).all()
        
        print(f"VIDEO CORPUS AUDIT REPORT")
        print("=" * 140)
        print(f"{'ID':<4} | {'Filename':<50} | {'Status':<8} | {'Trascr?':<8} | {'Summary?':<8} | {'Metadata Keys'}")
        print("-" * 140)
        
        missing_content_count = 0
        
        for v in videos:
            has_transcript = "YES" if v.transcript_text and len(v.transcript_text) > 10 else "NO"
            
            meta = v.metadata_json or {}
            has_summary = "YES" if meta.get("summary") and len(meta.get("summary")) > 10 else "NO"
            
            # Check for other common keys if they exist
            keys = list(meta.keys())
            keys_str = ", ".join(keys) if keys else "None"
            
            # Flagging logic
            if v.status == "READY":
                if has_transcript == "NO" or has_summary == "NO":
                    missing_content_count += 1
                    # Highlight row
                    print(f"\033[91m{v.id:<4} | {v.filename[:50]:<50} | {v.status:<8} | {has_transcript:<8} | {has_summary:<8} | {keys_str}\033[0m")
                else:
                    print(f"{v.id:<4} | {v.filename[:50]:<50} | {v.status:<8} | {has_transcript:<8} | {has_summary:<8} | {keys_str}")
            else:
                # Non-ready videos
                print(f"{v.id:<4} | {v.filename[:50]:<50} | {v.status:<8} | {has_transcript:<8} | {has_summary:<8} | {keys_str}")

        print("=" * 140)
        if missing_content_count == 0:
            print("✅ ALL READY VIDEOS HAVE FULL CONTENT (Transcript + Summary).")
        else:
            print(f"❌ FOUND {missing_content_count} READY VIDEOS WITH MISSING CONTENT.")
            print("   Please re-run analysis/ingestion for these files.")
            
    finally:
        db.close()

if __name__ == "__main__":
    audit_video_content()
