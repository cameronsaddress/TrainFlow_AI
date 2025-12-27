
import os
import sys
import sqlalchemy
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
print(f"DEBUG: Using DATABASE_URL={DATABASE_URL}")

def migrate():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("DEBUG: Connected to DB.")
        try:
            # Check if column exists
            sql_check = text("SELECT column_name FROM information_schema.columns WHERE table_name='video_corpus' AND column_name='is_archived'")
            result = conn.execute(sql_check)
            row = result.fetchone()
            
            if row:
                print("DEBUG: Column 'is_archived' ALREADY EXISTS.")
            else:
                print("DEBUG: Column 'is_archived' MISSING. Adding it now...")
                try:
                    conn.execute(text("ALTER TABLE video_corpus ADD COLUMN is_archived BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("SUCCESS: Column added.")
                except Exception as e:
                    print(f"ERROR: Failed to add column: {e}")
                    raise e
                    
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            sys.exit(1)
            
if __name__ == "__main__":
    migrate()
