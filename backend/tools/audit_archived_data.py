
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def audit_data():
    print("AUDITING ARCHIVED VIDEO DATA INTEGRITY...")
    
    # Check specifically for the Utility videos
    sql = text("""
        SELECT filename, 
               LENGTH(COALESCE(transcript_text, '')) as trans_len, 
               -- Fix: Cast column to text if needed or just use jsonb_array_length directly with a safe fallback
               -- We'll assume ocr_json is JSON type in DB, but let's be safe
               CASE WHEN ocr_json IS NULL THEN 0 ELSE json_array_length(ocr_json) END as ocr_count,
               is_archived
        FROM video_corpus 
        WHERE is_archived = true
        LIMIT 20
    """)
    
    results = db.execute(sql).fetchall()
    
    if not results:
        print("CRITICAL: No archived videos found!")
        return

    print(f"{'FILENAME':<50} | {'TRANSCRIPT CHECKSUM':<20} | {'OCR EVENTS':<10}")
    print("-" * 90)
    
    safe_count = 0
    for r in results:
        filename = r[0]
        trans_len = r[1]
        ocr_count = r[2]
        
        status = "SAFE" if trans_len > 0 else "EMPTY"
        print(f"{filename[:47]:<50} | {trans_len:<20} | {ocr_count:<10}")
        
        if trans_len > 0:
            safe_count += 1
            
    print("-" * 90)
    print(f"SUMMARY: {safe_count}/{len(results)} sampled archived videos have DATA.")

if __name__ == "__main__":
    audit_data()
