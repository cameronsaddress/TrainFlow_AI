import os
import logging
from sqlalchemy.orm import Session
from uuid import uuid4
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
# from ..services import llm # We will reuse the LLM service
from ..models import knowledge as k_models
from ..db import SessionLocal
import json

# Setup
logger = logging.getLogger(__name__)

def ingest_document(doc_id: int):
    """
    Background Task: Encapsulates PDF -> Text -> Chunks -> Embeddings -> Rules
    """
    print(f"Background Task Started: Ingesting Doc ID {doc_id}", flush=True)
    db = SessionLocal()
    try:
        doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
        if not doc:
            print(f"Doc ID {doc_id} not found in DB", flush=True)
            return
            
        doc.status = k_models.DocStatus.INDEXING
        db.commit()

        # 1. Load & Extract Text
        # Assuming local path or downloaded from MinIO to local
        if not os.path.exists(doc.file_path):
             raise FileNotFoundError(f"File {doc.file_path} not found")
        
        print(f"Loading PDF: {doc.file_path}", flush=True)
        reader = PdfReader(doc.file_path)
        full_text = ""
        page_count = len(reader.pages)
        print(f"Extracting text from {page_count} pages...", flush=True)
        
        for i, page in enumerate(reader.pages):
            full_text += page.extract_text() + "\n"
            if i % 50 == 0:
                print(f"Extracted page {i}/{page_count}...", flush=True)

        # 2. Chunking
        print(f"Chunking {len(full_text)} characters...", flush=True)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        texts = splitter.split_text(full_text)
        
        # 3. Embeddings (Mocked for now or call LLM service)
        # TODO: Implement real embedding call via 'llm.get_embedding(text)'
        # For prototype, we will just store text.
        
        for t in texts:
            chunk = k_models.KnowledgeChunk(
                document_id=doc.id,
                content=t,
                embedding=None, # Pending calc
                metadata_json={"source": "pdf"}
            )
            db.add(chunk)
            
        # 4. Independent Rule Extraction (LLM) - Scaled for Large Docs
        from ..services import llm
        import json
        import re

        # Process in large batches (Gemini Flash can handle 1M tokens, so ~200k chars is safe and efficient)
        BATCH_SIZE = 200000
        total_extracted = 0
        
        # Calculate total batches for logging
        total_batches = (len(full_text) // BATCH_SIZE) + 1
        print(f"Starting Rule Extraction for Doc {doc_id}. Total Text: {len(full_text)} chars. Batches: {total_batches}", flush=True)

        for i in range(0, len(full_text), BATCH_SIZE):
            batch_num = (i // BATCH_SIZE) + 1
            batch_text = full_text[i : i + BATCH_SIZE]
            
            prompt = f"""
            Analyze the following Standard Operating Procedure (SOP) text (Batch {batch_num}/{total_batches}).
            Extract a list of specific "Business Rules" or "Compliance Checks".
            Format as JSON list: [{{ "trigger": "Context (e.g. Login Screen)", "rule": "Description of rule", "type": "FORMAT|SEQUENCE|COMPLIANCE" }}]
            
            Text:
            {batch_text}
            """
            
            print(f"Processing Batch {batch_num}/{total_batches}...", flush=True)
            
            try:
                response = llm.generate_text(prompt)
                
                # Robust JSON parsing
                clean_response = response.strip()
                if "```" in clean_response:
                    match = re.search(r'```(?:json)?\s*(.*?)```', clean_response, re.DOTALL)
                    if match:
                        clean_response = match.group(1).strip()
                
                # Sanitize common LLM quirks
                clean_response = clean_response.replace(",]", "]") 
                
                rules_data = []
                try:
                    rules_data = json.loads(clean_response)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON for batch {batch_num}. Response: {response[:100]}...", flush=True)
                    continue

                if isinstance(rules_data, list):
                    for r in rules_data:
                        rule = k_models.BusinessRule(
                            document_id=doc.id,
                            trigger_context=r.get("trigger", "General"),
                            rule_description=r.get("rule", "Unknown Rule"),
                            rule_type=r.get("type", "COMPLIANCE")
                        )
                        db.add(rule)
                        total_extracted += 1
                    db.commit() # Commit per batch to save progress
                    
            except Exception as batch_e:
                print(f"Error processing batch {batch_num}: {batch_e}", flush=True)
                continue

        print(f"Extracted {total_extracted} total rules from Doc {doc_id}", flush=True)
        
        doc.status = k_models.DocStatus.READY
        db.commit()
            

    except Exception as e:
        print(f"Ingestion Failed: {e}", flush=True)
        doc.status = k_models.DocStatus.FAILED
        doc.error_message = str(e)
        db.commit()
    finally:
        db.close()

