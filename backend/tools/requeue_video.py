
import os
import sys
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import knowledge as k_models

# Setup DB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Setup Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.from_url(REDIS_URL)

FILENAME = "The_3_Most_Important_Jiu_Jitsu_Techniques_For_A_BJJ_White_Belt_by_John_Danaher.mp4"

def requeue():
    print(f"Searching for {FILENAME}...")
    video = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename == FILENAME).first()
    
    if not video:
        print("Video NOT FOUND in DB.")
        sys.exit(1)
        
    print(f"Found Video ID: {video.id} | Status: {video.status} | Archived: {video.is_archived}")
    
    # Reset
    video.status = k_models.DocStatus.PENDING
    video.is_archived = False
    video.error_message = None # Clear old errors
    db.commit()
    print("Updated Status to PENDING and Unarchived.")
    
    # Dispatch
    r.publish("corpus_jobs", str(video.id))
    print(f"Dispatched Job {video.id} to 'corpus_jobs' Redis channel.")

if __name__ == "__main__":
    requeue()
