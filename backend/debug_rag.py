
import sys
import os

# Add backend to path
sys.path.append('/app')
sys.path.append('/home/canderson/TrainFlow_AI/backend')

from app.db import SessionLocal
from app.models import knowledge as k_models
from sqlalchemy import or_

def test_search():
    db = SessionLocal()
    query = "How do I replace an insulator?"
    
    # 1. Simulate Term Extraction (Hardcoded for now to what LLM likely gives)
    terms = ["insulator", "replace", "repair", "procedure", "steps"]
    print(f"Terms: {terms}")
    
    # 2. Search Chunks
    chunk_filters = [k_models.KnowledgeChunk.content.ilike(f"%{term}%") for term in terms]
    
    # Naive OR search
    results = db.query(k_models.KnowledgeChunk)\
        .filter(or_(*chunk_filters))\
        .limit(15)\
        .all()
        
    print(f"\nFound {len(results)} chunks:")
    for i, r in enumerate(results):
        # Fetch document name
        doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == r.document_id).first()
        doc_name = doc.filename if doc else "Unknown"
        
        print(f"[{i+1}] Doc: {doc_name} | Content Preview: {r.content[:100]}...")

if __name__ == "__main__":
    test_search()
