import sys
import os
import json
import re

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func

def hydrate_transcripts():
    print("💧 Starting Transcript Hydration for Curriculum 11...", flush=True)
    db = SessionLocal()
    try:
        curriculum = db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).first()
        if not curriculum:
            print("❌ No curriculum found.")
            return

        data = curriculum.structured_json
        modules = data.get("modules", [])
        
        fixed_count = 0
        
        # Pre-load video map for speed
        all_videos = db.query(k_models.VideoCorpus).all()
        video_map = {v.filename: v for v in all_videos} # Exact match
        
        # Helper for fuzzy finding
        def find_video(fname):
            if fname in video_map: return video_map[fname]
            # Try fuzzy (space/underscore)
            alt = fname.replace(" ", "_")
            if alt in video_map: return video_map[alt]
            alt = fname.replace("_", " ")
            if alt in video_map: return video_map[alt]
            return None

        for m in modules:
            for l in m.get("lessons", []):
                
                # Check if we need to hydrate (or re-hydrate to be safe)
                # if "transcript_text" in l and len(l["transcript_text"]) > 10:
                #    continue 

                sources = l.get("source_clips", [])
                if not sources:
                    continue
                    
                clip = sources[0]
                fname = clip.get("video_filename")
                # Cast lesson clips timestamps to float
                try:
                    start = float(clip.get("start_time", 0))
                    end = float(clip.get("end_time", 0))
                except (ValueError, TypeError):
                    print(f"⚠️ Invalid start/end times for lesson {l.get('title')}: {clip.get('start_time')}-{clip.get('end_time')}")
                    continue

                if not fname:
                    continue
                    
                video = find_video(fname)
                if not video:
                    print(f"⚠️ Video not found for lesson '{l.get('title')}': {fname}")
                    continue
                    
                # Extract Transcript
                t_json = video.transcript_json
                # if not t_json:
                #    print(f"⚠️ No transcript_json for video: {fname}")
                #    continue
                
                # Slicing Logic
                extracted_text = []
                
                # Handle possible formats
                segments = []
                if isinstance(t_json, list):
                    segments = t_json
                elif isinstance(t_json, dict) and "segments" in t_json:
                    segments = t_json["segments"]
                elif isinstance(t_json, dict) and "text" in t_json:
                     # Fallback to full text if no segments (rare)
                     pass

                full_text = ""
                
                if segments:
                    for seg in segments:
                        # Whisper segment: {start, end, text}
                        try:
                            s_start = float(seg.get("start", 0))
                            s_end = float(seg.get("end", 0))
                            text = seg.get("text", "").strip()
                            
                            # Strict containment or slight overlap?
                            # Let's say if midpoint is in range
                            midpoint = (s_start + s_end) / 2
                            if start <= midpoint <= end:
                                 extracted_text.append(text)
                        except (ValueError, TypeError):
                            continue
                    
                    full_text = " ".join(extracted_text)
                
                # --- FUZZY FALLBACK ---
                # If segment matching failed (or no segments), try proportional slicing
                if not full_text: 
                    # print(f"   ⚠️ No overlapping segments for {fname}. Attempting fuzzy slice...")
                    if video.transcript_text and video.duration_seconds and video.duration_seconds > 0:
                        txt_len = len(video.transcript_text)
                        
                        # Ratio
                        start_pct = max(0.0, start / video.duration_seconds)
                        end_pct = min(1.0, end / video.duration_seconds)
                        
                        char_start = int(txt_len * start_pct)
                        char_end = int(txt_len * end_pct)
                        
                        # Ensure sanity
                        if char_end > char_start:
                             # Add a small buffer or clamp? 
                             # Just slice
                             slice = video.transcript_text[char_start:char_end]
                             full_text = f"[Approximated Transcript] ... {slice} ..."
                        else:
                             full_text = ""
                    else:
                        full_text = ""

                if full_text:
                    l["transcript_text"] = full_text
                    fixed_count += 1
                    # print(f"   ✅ Hydrated {len(full_text)} chars for: {l.get('title')}")
                else:
                    print(f"   ⚠️ No overlapping text found for {fname} ({start}-{end})")

        if fixed_count > 0:
            curriculum.structured_json = data
            flag_modified(curriculum, "structured_json")
            db.commit()
            print(f"✅ Hydration Complete. Updated {fixed_count} lessons with original transcripts.")
        else:
            print("✨ No updates needed.")

    finally:
        db.close()

if __name__ == "__main__":
    hydrate_transcripts()
