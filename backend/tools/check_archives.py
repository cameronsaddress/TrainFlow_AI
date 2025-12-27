
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def check_archives():
    print("Checking for archived videos...")
    sql = text("SELECT id, filename, is_archived, status FROM video_corpus WHERE is_archived = true")
    results = db.execute(sql).fetchall()
    
    if results:
        print(f"FOUND {len(results)} ARCHIVED VIDEOS:")
        for r in results:
            print(f" - {r[1]} (Status: {r[3]})")
    else:
        print("NO ARCHIVED VIDEOS FOUND.")

if __name__ == "__main__":
    check_archives()
