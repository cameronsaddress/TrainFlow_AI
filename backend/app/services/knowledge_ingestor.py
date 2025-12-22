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

async def ingest_document(doc_id: int):
    """
    Background Task: Encapsulates PDF -> Text -> Chunks -> Embeddings -> Rules
    """
    db = SessionLocal()
    try:
        doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
        if not doc:
            return
            
        doc.status = k_models.DocStatus.INDEXING
        db.commit()

        # 1. Load & Extract Text
        # Assuming local path or downloaded from MinIO to local
        if not os.path.exists(doc.file_path):
             raise FileNotFoundError(f"File {doc.file_path} not found")
        
        reader = PdfReader(doc.file_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"

        # 2. Chunking
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
            
        # 4. Independent Rule Extraction (LLM)
        # Call LLM to extract specific rules from full text
        from ..services import llm
        
        prompt = f"""
        Analyze the following Standard Operating Procedure (SOP) text.
        Extract a list of specific "Business Rules" or "Compliance Checks".
        Format as JSON list: [{{ "trigger": "Context (e.g. Login Screen)", "rule": "Description of rule", "type": "FORMAT|SEQUENCE|COMPLIANCE" }}]
        
        Text:
        {full_text[:4000]}... (truncated)
        """
        
        response = "No response"
        try:
            # We assume llm.generate returns string
            response = llm.generate_text(prompt)
            logger.info(f"Raw LLM Response for Doc {doc_id}: {response}")
            
            # Robust JSON parsing: Remove Markdown code blocks if present
            clean_response = response.strip()
            if "```" in clean_response:
                import re
                # Extract content between ```json ... ``` or just ``` ... ```
                match = re.search(r'```(?:json)?\s*(.*?)```', clean_response, re.DOTALL)
                if match:
                    clean_response = match.group(1).strip()
            
            # Attempt parsing
            import json
            # Sanitize common LLM quirks (trailing commas)
            clean_response = clean_response.replace(",]", "]") 
            
            rules_data = json.loads(clean_response)
            
            # Validate and Insert
            count = 0
            if isinstance(rules_data, list):
                for r in rules_data:
                    rule = k_models.BusinessRule(
                        document_id=doc.id,
                        trigger_context=r.get("trigger", "General"),
                        rule_description=r.get("rule", "Unknown Rule"),
                        rule_type=r.get("type", "COMPLIANCE")
                    )
                    db.add(rule)
                    count += 1
            logger.info(f"Extracted {count} rules from Doc {doc_id}")
            
            doc.status = k_models.DocStatus.READY
            db.commit()
            
        except Exception as e:
            logger.error(f"Rule Extraction failed: {e}. Raw Response: {response}")
            # Ensure we mark as ready even if rule extraction fails? 
            # Or mark as PARTIAL? For now, let's just log and keep doc as READY 
            # but maybe with a warning?
            # Actually, the outer try/except handles the 'Ingestion Failed' status.
            # This inner try/except (lines 68-108) wraps ONLY rule extraction.
            # If Rule Extraction fails, we still want the doc to be indexed (Chunks are done).
            
            # So we should NOT mark as FAILED here if chunks succeeded.
            doc.status = k_models.DocStatus.READY
            doc.error_message = f"Rule Extraction Failed: {str(e)}"
            db.commit()

    except Exception as e:
        logger.error(f"Ingestion Failed: {e}")
        doc.status = k_models.DocStatus.FAILED
        doc.error_message = str(e)
        db.commit()
    finally:
        db.close()

