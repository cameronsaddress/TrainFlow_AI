import sys
import os

# Add parent dir to path to find app packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import knowledge_ingestor

def reingest_all():
    db = SessionLocal()
    try:
        docs = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.status != k_models.DocStatus.FAILED).all()
        print(f"Found {len(docs)} documents to re-ingest.")
        
        for doc in docs:
            print(f"--- Re-ingesting Doc ID {doc.id}: {doc.filename} ---")
            
            # Clean up old chunks/rules first?
            # Ingestor appends... we should probably clear old chunks first to avoid duplicates.
            # But the ingestor doesn't have clear logic exposed.
            # Let's manually delete chunks/rules for this doc before re-running.
            
            num_chunks = db.query(k_models.KnowledgeChunk).filter(k_models.KnowledgeChunk.document_id == doc.id).delete()
            num_rules = db.query(k_models.BusinessRule).filter(k_models.BusinessRule.document_id == doc.id).delete()
            db.commit()
            
            print(f"Deleted {num_chunks} old chunks and {num_rules} old rules.")
            
            # Run ingestion
            knowledge_ingestor.ingest_document(doc.id)
            print("Done.\n")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reingest_all()
