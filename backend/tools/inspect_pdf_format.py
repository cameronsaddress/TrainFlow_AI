import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append('/app')
from app.db import SessionLocal

def main():
    db = SessionLocal()
    try:
        # Fetch PDF Text (ID 10)
        res = db.execute(text("SELECT extracted_text FROM knowledge_documents WHERE id = 10")).fetchone()
        if not res:
            print("No doc found")
            return
        
        full_text = res[0]
        print(f"Total Length: {len(full_text)}")
        print("--- First 3000 chars ---")
        print(full_text[:3000])
        print("--- Regex Check for 'Page' ---")
        import re
        matches = list(re.finditer(r'(Page\s+\d+|^\d+\s*$)', full_text, re.MULTILINE))
        print(f"Found {len(matches)} page-like markers.")
        for m in matches[:10]:
            print(f"Match: '{m.group(0)}' at {m.start()}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
