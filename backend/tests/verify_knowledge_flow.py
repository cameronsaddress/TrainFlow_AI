import requests
import time
import os
from fpdf import FPDF

API_URL = "http://localhost:8000/api"

def create_dummy_pdf(filename="test_sop.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    text = """
    National Grid Standard Operating Procedure
    
    1. Login Procedures
    - Navigate to https://webaccess.ngrid.com/
    - Enter Username and Password.
    - Context: Login Screen
    - Rule: Must use 6-digit token code.
    
    2. GIS Updates
    - Open Smallworld GIS.
    - Context: GIS Editor
    - Rule: Update all poles with Major Equipment.
    - Rule: Do not update Cancelled Poles.
    
    3. Help Desk
    - For STORMS issues, call 1-877-373-1112.
    """
    
    pdf.multi_cell(0, 10, text)
    pdf.output(filename)
    return filename

def test_knowledge_flow():
    print("--- Starting Knowledge Engine Verification ---")
    
    # 1. Create PDF
    pdf_path = create_dummy_pdf()
    print(f"[+] Created dummy PDF: {pdf_path}")
    
    # 2. Upload
    print("[*] Uploading PDF...")
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        try:
            res = requests.post(f"{API_URL}/knowledge/upload", files=files)
            res.raise_for_status()
            data = res.json()
            doc_id = data['id']
            print(f"[+] Upload Success. Doc ID: {doc_id}")
        except Exception as e:
            print(f"[-] Upload Failed: {e}")
            return

    # 3. Poll for Ingestion
    print("[*] Waiting for Ingestion...")
    for _ in range(10): # Wait up to 20s
        res = requests.get(f"{API_URL}/knowledge/documents")
        docs = res.json()
        my_doc = next((d for d in docs if d['id'] == doc_id), None)
        
        status = my_doc['status']
        print(f"    Status: {status}")
        
        if status == 'READY':
            print("[+] Ingestion Complete.")
            break
        if status == 'FAILED':
            print(f"[-] Ingestion Failed: {my_doc.get('error_message')}")
            return
        time.sleep(2)
        
    # 4. Verify Rules
    print("[*] Verifying Rule Extraction...")
    res = requests.get(f"{API_URL}/knowledge/rules")
    rules = res.json()
    print(f"    Found {len(rules)} rules.")
    for r in rules:
        if r['document_id'] == doc_id:
            print(f"    - [{r['rule_type']}] {r['trigger_context']}: {r['rule_description']}")
            
    if len(rules) == 0:
        print("[-] Warning: No rules extracted. (LLM might be mocking or failed)")
    else:
        print("[+] Rules verification passed.")

    # 5. Verify Context (RAG/Search)
    print("[*] Verifying Context Query (Smart Player)...")
    query = {"text": "Login"}
    res = requests.post(f"{API_URL}/knowledge/context", json=query)
    chunks = res.json()
    print(f"    Found {len(chunks)} chunks for query 'Login'.")
    
    if len(chunks) > 0:
        print(f"    - Top Result: {chunks[0]['content'][:100]}...")
        print("[+] Context verification passed.")
    else:
        print("[-] No chunks found. Keyword search failed?")

if __name__ == "__main__":
    test_knowledge_flow()
