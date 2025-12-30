import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

def main():
    db = SessionLocal()
    try:
        doc = db.query(k_models.KnowledgeDocument).get(10)
        text = doc.extracted_text
        lower_text = text.lower()
        
        print(f"Total Text Length: {len(text)}")
        
        def find_hits(term, label):
            print(f"--- Searching for '{label}' ---")
            p = 0
            count = 0
            while count < 10:
                idx = lower_text.find(term.lower(), p)
                if idx == -1: break
                print(f"[{count}] Found at {idx}")
                print(f"CTX: {text[idx:idx+80].replace(chr(10), ' ')}...")
                p = idx + 1
                count += 1

        find_hits("section 1", "Section 1")
        find_hits("section 2", "Section 2")
        find_hits("1.3 TRANSMISSION VOLTAGES", "Specific Anchor")
        find_hits("Foreword and Purpose", "Lesson 1 Anchor")

    finally:
        db.close()

if __name__ == "__main__":
    main()
