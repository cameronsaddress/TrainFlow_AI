
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def swap_corpus():
    print("SWAPPING CORPUS: RESTORING UTILITY VIDEOS...")
    
    # 1. Archive BJJ Videos (Current Active)
    # We recognize them because they are NOT archived.
    print("  > Archiving current active videos (BJJ)...")
    sql_archive = text("UPDATE video_corpus SET is_archived = true WHERE is_archived = false")
    result_archive = db.execute(sql_archive)
    print(f"    Archived {result_archive.rowcount} BJJ videos.")
    
    # 2. Unarchive Utility Videos (Current Archived)
    # We recognize them because they ARE archived.
    # NOTE: This unarchives ALL archived videos. 
    # Since we just archived BJJ, we need to be careful not to unarchive them immediately.
    # The previous step committed? No, assume implicit transaction if using execute directly? 
    # SQLAlchemy session needs commit.
    
    # Improved Logic:
    # 1. Get IDs of currently active (BJJ)
    bjj_ids = [r[0] for r in db.execute(text("SELECT id FROM video_corpus WHERE is_archived = false")).fetchall()]
    print(f"    Identified {len(bjj_ids)} BJJ videos to archive.")
    
    # 2. Get IDs of currently archived (Utility)
    utility_ids = [r[0] for r in db.execute(text("SELECT id FROM video_corpus WHERE is_archived = true")).fetchall()]
    print(f"    Identified {len(utility_ids)} Utility videos to restore.")
    
    if not utility_ids:
        print("    CRITICAL: No utility videos found in archive! Aborting swap.")
        return

    # 3. Perform Swap
    if bjj_ids:
        db.execute(text("UPDATE video_corpus SET is_archived = true WHERE id IN :ids"), {"ids": tuple(bjj_ids)})
    
    db.execute(text("UPDATE video_corpus SET is_archived = false WHERE id IN :ids"), {"ids": tuple(utility_ids)})
    
    db.commit()
    print("  > SWAP COMPLETE. Utility videos are now ACTIVE.")

if __name__ == "__main__":
    swap_corpus()
