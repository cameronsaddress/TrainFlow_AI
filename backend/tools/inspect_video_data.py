import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models.knowledge import VideoCorpus
import json

db = SessionLocal()
video = db.query(VideoCorpus).filter(VideoCorpus.transcript_json != None).first()

if video:
    print(f"Found Video: {video.filename}")
    print(f"Transcript JSON keys: {video.transcript_json.keys() if isinstance(video.transcript_json, dict) else 'Not a dict'}")
    # Print sample to see structure
    print(json.dumps(video.transcript_json, indent=2)[:500])
else:
    print("No videos with transcript_json found.")
    
# check transcript_text
video_text = db.query(VideoCorpus).filter(VideoCorpus.transcript_text != None).first()
if video_text:
    print(f"\nFound Video with Text: {video_text.filename}")
    print(f"Text Preview: {video_text.transcript_text[:200]}")
