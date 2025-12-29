
import os
import glob
from pypdf import PdfReader

DATA_DIR = "/app/data/knowledge"

def test_search_file(file_path, anchor_text):
    print(f"\n--- Testing File: {os.path.basename(file_path)} ---")
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return

    anchor_lower = anchor_text.lower()
    
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
        except:
            continue
            
        if not text: 
            continue
            
        text_lower = text.lower()
        
        # Heuristic 1: Skip obvious TOC pages
        if "table of contents" in text_lower[:500]:
            print(f"Page {i+1}: SKIPPED (Detected TOC Header via 'table of contents')")
            continue

        # Fuzzy Logic Mirror
        import re
        def tokens(s): return re.findall(r'\w+', s.lower())
        
        anchor_tokens = tokens(anchor_text)
        text_tokens = tokens(text_lower)
        anchor_norm = " ".join(anchor_tokens)
        
        # Check matching lines fuzzily
        match_found = False
        for line in text_lower.split('\n'):
            line_tokens = tokens(line)
            line_norm = " ".join(line_tokens)
            
            if anchor_norm in line_norm:
                clean = line.strip()
                if clean and (clean[-1].isdigit() or clean.endswith("thru") or "..." in clean):
                     print(f"Page {i+1}: SKIPPED (Detected TOC Line match: '{clean}')")
                     match_found = False
                     continue
                
                print(f"Page {i+1}: FOUND MATCH (Content) via Fuzzy: '{clean}'")
                return


    # Debugging: Focus on Pages 19-23 where we expect the header
    print(f"DEBUG: Analying Pages 19-23 in {os.path.basename(file_path)}...")
    for i, page in enumerate(reader.pages):
        if i < 19 or i > 23: continue
        
        try:
            text = page.extract_text() or ""
            text_lower = text.lower()
            
            print(f"--- Page {i+1} Text Start ---")
            print(text_lower[:500]) # Print first 500 chars to see headers
            print(f"--- Page {i+1} Text End ---")
            
            if "1.4" in text_lower:
                print(f"DEBUG Page {i+1}: Contains '1.4'")

        except:
            pass

    print("Search Completed.")

if __name__ == "__main__":
    pdf_files = glob.glob(os.path.join(DATA_DIR, "*.pdf"))
    targets = ["1.3 TRANSMISSION VOLTAGES", "1.4 Sub-Transmission Voltages"]
    
    print(f"Scanning {len(pdf_files)} PDFs...")
    
    for f in pdf_files:
        for t in targets:
            test_search_file(f, t)
