
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def fix_swap():
    print("CORRECTING CORPUS SWAP...")
    
    # 1. Archive EVERYTHING first
    print("  > Archiving ALL videos...")
    db.execute(text("UPDATE video_corpus SET is_archived = true"))
    
    # 2. Unarchive ONLY Utility videos
    # Keywords based on previous audit
    keywords = [
        "Work Order", "PCO", "GIS", "OneDrive", "EON", "Sketches", 
        "DigSafes", "Make Ready", "CustomerOutage", "Meeting Recording"
    ]
    
    print(f"  > Unarchiving videos matching: {keywords}")
    
    conditions = " OR ".join([f"filename ILIKE '%{k}%'" for k in keywords])
    sql = text(f"UPDATE video_corpus SET is_archived = false WHERE {conditions}")
    
    result = db.execute(sql)
    db.commit()
    print(f"  > RESTORED {result.rowcount} Utility Videos.")
    
    # Verify BJJ are archived
    bjj_check = db.execute(text("SELECT count(*) FROM video_corpus WHERE is_archived = false AND filename ILIKE '%Jiu%'")).scalar()
    print(f"  > Active BJJ Videos (Should be 0): {bjj_check}")

if __name__ == "__main__":
    fix_swap()
