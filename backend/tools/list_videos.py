import sys
sys.path.append("/app")

from app.db import SessionLocal
from app.models.knowledge import VideoCorpus

db = SessionLocal()
videos = db.query(VideoCorpus).all()
print(f"Total Videos: {len(videos)}")
for v in videos:
    print(f" - {v.id}: {v.filename} ({len(v.transcript_text or '')} chars)")
