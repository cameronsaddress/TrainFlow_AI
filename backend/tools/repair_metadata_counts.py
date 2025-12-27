
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import knowledge as k_models

# Setup DB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def repair():
    print("Starting Metadata Repair for Word Counts...")
    videos = db.query(k_models.VideoCorpus).all()
    
    updated_count = 0
    for v in videos:
        # Check if already has it
        meta = v.metadata_json or {}
        if "word_count" in meta:
            print(f"Skipping {v.filename}: Has count {meta['word_count']}")
            continue
            
        print(f"Repairing {v.filename}...")
        
        # Calculate
        text = v.transcript_text or ""
        word_count = len(text.split()) if text else 0
        
        if word_count == 0 and v.status == k_models.DocStatus.READY:
            print(f"WARNING: {v.filename} is READY but has 0 words.")
        
        meta["word_count"] = word_count
        v.metadata_json = meta
        updated_count += 1
        
    db.commit()
    print(f"Repair Complete. Updated {updated_count} videos.")

if __name__ == "__main__":
    repair()
