from sqlalchemy import create_engine, text
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SQLALCHEMY_DATABASE_URL

def check_sizes():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    with engine.connect() as conn:
        # 1. Check Plan Size
        print("--- Curriculum Plans ---")
        result = conn.execute(text("SELECT id, title, length(structured_json::text) as size_bytes FROM training_curricula ORDER BY created_at DESC LIMIT 5"))
        for row in result:
            size_mb = row.size_bytes / (1024 * 1024) if row.size_bytes else 0
            print(f"ID: {row.id} | Title: {row.title} | Size: {size_mb:.2f} MB")

        # 2. Check Video Corpus Size (Total vs Deferrable)
        print("\n--- Video Corpus (Potential Overhead) ---")
        # Estimate size of transcript_text
        result = conn.execute(text("SELECT count(*) as count, sum(length(transcript_text)) as transcript_size FROM video_corpus"))
        row = result.fetchone()
        count = row.count
        transcript_mb = (row.transcript_size or 0) / (1024 * 1024)
        print(f"Total Videos: {count}")
        print(f"Total Transcript Text Size: {transcript_mb:.2f} MB (This is loaded on every request if not deferred!)")

if __name__ == "__main__":
    check_sizes()
