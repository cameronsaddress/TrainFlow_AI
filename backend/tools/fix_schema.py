import sys
import os

# Add parent dir to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import engine
from sqlalchemy import text

def update_schema():
    print("Attempting to update schema...")
    with engine.connect() as conn:
        # Add transcript_json
        try:
            conn.execute(text("ALTER TABLE video_corpus ADD COLUMN IF NOT EXISTS transcript_json JSON;"))
            print("Added transcript_json column.")
        except Exception as e:
            print(f"Error adding transcript_json: {e}")

        # Add ocr_json
        try:
            conn.execute(text("ALTER TABLE video_corpus ADD COLUMN IF NOT EXISTS ocr_json JSON;"))
            print("Added ocr_json column.")
        except Exception as e:
            print(f"Error adding ocr_json: {e}")
            
        conn.commit()
    print("Schema update complete.")

if __name__ == "__main__":
    update_schema()
