from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import knowledge as k_models
from ..services import knowledge_ingestor
import shutil
import os
import uuid

# Prefix set in main.py, but usually router-based
router = APIRouter(prefix="/knowledge", tags=["knowledge"])

DATA_DIR = "/app/data/knowledge"
os.makedirs(DATA_DIR, exist_ok=True)

@router.post("/context")
async def get_context(query: dict, db: Session = Depends(get_db)):
    """
    Retrieve relevant Knowledge Chunks based on a query text.
    Payload: {"text": "login screen"}
    """
    search_text = query.get("text", "")
    if not search_text:
        return []
    
    # 1. Vector Search (TODO: active when embeddings work)
    # 2. Keyword Search Fallback
    results = db.query(k_models.KnowledgeChunk)\
        .filter(k_models.KnowledgeChunk.content.ilike(f"%{search_text}%"))\
        .limit(3)\
        .all()
        
    return [
        {"content": r.content, "source_doc": r.document_id, "score": 0.8} 
        for r in results
    ]

@router.post("/upload")
async def upload_knowledge_doc(
    file: UploadFile = File(...), 
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Upload a PDF, save it, and trigger ingestion.
    """
    # 1. Save File
    file_ext = os.path.splitext(file.filename)[1]
    if file_ext.lower() != ".pdf":
        raise HTTPException(400, "Only PDF files supported currently")

    new_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(DATA_DIR, new_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. Create DB Entry
    doc = k_models.KnowledgeDocument(
        filename=file.filename,
        file_path=file_path,
        status=k_models.DocStatus.PENDING
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # 3. Trigger Ingestion (Async)
    background_tasks.add_task(knowledge_ingestor.ingest_document, doc.id)
    
    return {"status": "uploaded", "id": doc.id, "filename": doc.filename}

@router.get("/documents")
async def list_documents(db: Session = Depends(get_db)):
    """List all knowledge documents and statuses."""
    return db.query(k_models.KnowledgeDocument).order_by(k_models.KnowledgeDocument.created_at.desc()).all()

@router.get("/rules")
async def list_rules(db: Session = Depends(get_db)):
    """List all extracted compliance rules."""
    return db.query(k_models.BusinessRule).filter(k_models.BusinessRule.is_active == True).all()

@router.put("/rules/{rule_id}")
async def update_rule(rule_id: int, updates: dict, db: Session = Depends(get_db)):
    """Update rule (disable, edit text)."""
    rule = db.query(k_models.BusinessRule).filter(k_models.BusinessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    
    if "is_active" in updates:
        rule.is_active = updates["is_active"]
    if "rule_description" in updates:
        rule.rule_description = updates["rule_description"]
        
    db.commit()
    return rule
@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Delete a document and its file."""
    doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
        
    # Delete file from disk
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            print(f"Error deleting file {doc.file_path}: {e}")
            
    # Delete from DB
    db.delete(doc)
    db.commit()
    
    return {"status": "deleted", "id": doc_id}
