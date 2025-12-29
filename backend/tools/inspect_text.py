
import sys
import os
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

def inspect_text(doc_id):
    db = SessionLocal()
    try:
        doc = db.query(k_models.KnowledgeDocument).get(doc_id)
        if not doc or not doc.extracted_text:
            print(f"Document {doc_id} has no extracted text.")
            return

        text = doc.extracted_text
        print(f"Text Length: {len(text)}")
        
        # Check for Null Bytes
        null_count = text.count('\x00')
        print(f"Null Bytes (\\x00): {null_count}")
        
        # Check for other control chars (excluding \n, \t, \r)
        control_chars = [c for c in text if (ord(c) < 32 and c not in ('\n', '\t', '\r'))]
        print(f"Control Chars (non-whitespace): {len(control_chars)}")
        if len(control_chars) > 0:
            print(f"Sample Control Chars: {[ord(c) for c in control_chars[:10]]}")

        # Check for replacement chars
        replacement_count = text.count('\ufffd')
        print(f"Replacement Chars (\\ufffd): {replacement_count}")

        # Sample start/end
        print("\n--- Start Sample ---")
        print(text[:200])
        print("\n--- End Sample ---")
        print(text[-200:])

    finally:
        db.close()

if __name__ == "__main__":
    inspect_text(2) # Assuming Document 2 or relevant ID. 
    # Wait, previous logs said Document 10.
    print("\n--- Inspecting Document 10 ---")
    inspect_text(10)
