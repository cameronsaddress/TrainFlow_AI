from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import knowledge as k_models
from ..services import knowledge_ingestor
from ..services import llm
import shutil
import os
import uuid
import json

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

@router.get("/glossary")
async def list_glossary(db: Session = Depends(get_db)):
    """List all glossary/troubleshooting entries."""
    return db.query(k_models.GlossaryEntry).all()

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

    return {
        "answer": final_answer,
        "sources": [c.document_id for c in relevant_chunks]
    }

@router.get("/documents/{doc_id}/pages/{page_num}/stream")
async def stream_document_page(doc_id: int, page_num: int, db: Session = Depends(get_db)):
    """
    Smart Stream: Extracts ONLY the requested page (+/- context optional) 
    and streams it as a lightweight PDF.
    """
    doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, "Document file not found")

    try:
        from pypdf import PdfReader, PdfWriter
        from io import BytesIO
        from fastapi.responses import StreamingResponse

        reader = PdfReader(doc.file_path)
        total_pages = len(reader.pages)
        
        if page_num < 1 or page_num > total_pages:
             # Fallback to page 1 if out of bounds
             page_num = 1
             
        writer = PdfWriter()
        
        # 0-indexed adjustment
        target_idx = page_num - 1
        
        # Context Buffer: +/- 5 pages
        start_idx = max(0, target_idx - 5)
        end_idx = min(total_pages, target_idx + 6) # slice is exclusive at end
        
        # Add pages in range
        for i in range(start_idx, end_idx):
            writer.add_page(reader.pages[i])
        
        output_stream = BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)
        
        return StreamingResponse(
            output_stream, 
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={doc.filename}_p{page_num}.pdf"}
        )
        
    except Exception as e:
        print(f"Smart Stream Error: {e}")
        # Fallback to full file if slicing fails
        from fastapi.responses import FileResponse
        return FileResponse(doc.file_path, filename=doc.filename, media_type="application/pdf", content_disposition_type="inline")

@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: int, db: Session = Depends(get_db)):
    """Convert DB ID to file download."""
    doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, "Document file not found")
        
    from fastapi.responses import FileResponse
    return FileResponse(doc.file_path, filename=doc.filename, media_type="application/pdf", content_disposition_type="inline")


# --- ASK TRAINFLOW (RAG CHAT) ---

from pydantic import BaseModel
from datetime import datetime, timedelta

class AskRequest(BaseModel):
    query: str
    session_id: str = "guest" # Simple session tracking

# In-Memory Rate Limiter (MVP)
# Map: session_id -> { count: int, start_time: datetime }
RATE_LIMIT_STORE = {}
RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW_SECONDS = 3600 # 1 hour

@router.post("/ask")
async def ask_trainflow(payload: AskRequest, db: Session = Depends(get_db)):
    """
    RAG-powered Q&A using DeepSeek-V3.
    """
    # 1. Rate Check
    now = datetime.utcnow()
    user_limit = RATE_LIMIT_STORE.get(payload.session_id)
    
    if user_limit:
        # Check window reset
        if (now - user_limit["start_time"]).total_seconds() > RATE_LIMIT_WINDOW_SECONDS:
            user_limit = {"count": 1, "start_time": now}
        else:
            if user_limit["count"] >= RATE_LIMIT_MAX:
                raise HTTPException(429, "Rate limit exceeded (30 queries/hour). Please try again later.")
            user_limit["count"] += 1
    else:
        user_limit = {"count": 1, "start_time": now}
        
    RATE_LIMIT_STORE[payload.session_id] = user_limit
    
    # 2. Retrieval (Hybrid/Keyword Fallback)
    # Ideally use vector search, but for now we look for keywords in Chunks & Rules
    
    # Improved: Extract keywords using LLM with Subject/Intent separation
    try:
        # Prompt refined to separate the CORE subject from the INTENT
        # This prevents generic "steps" from matching unrelated docs
        structure_prompt = f"""
        Analyze this query: "{payload.query}"
        Return a JSON object with:
        - "subject": The main technical object (e.g., "insulator", "transformer", "pole").
        - "intent": The action or type of info (e.g., "repair", "replace", "steps", "procedure").
        - "keywords": A list of 3-5 specific keywords for search.
        Return ONLY valid JSON.
        """
        # Use x-ai/grok-4.1-fast model
        response_text = llm.generate_text(
            prompt=structure_prompt,
            model="x-ai/grok-4.1-fast"
        ).strip()
        
        # Clean markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        try:
            extraction = json.loads(response_text)
            subject = extraction.get("subject", "")
            # Handle if intent is list or string
            raw_intent = extraction.get("intent", [])
            keywords = extraction.get("keywords", [])
            
            intent_terms = (raw_intent if isinstance(raw_intent, list) else [raw_intent]) + keywords
            
            if subject and len(subject) > 2:
                 print(f"DEBUG: Smart Search Active. Subject: {subject} | Intent: {intent_terms}")
            else:
                 subject = payload.query
                 intent_terms = []

        except json.JSONDecodeError:
            print(f"JSON Parse Error. Raw LLM response: {response_text}")
            # Naive cleanup fallback
            clean_q = payload.query.lower().replace("how to", "").replace("how do i", "").strip()
            subject = clean_q if clean_q else payload.query
            intent_terms = []
            print(f"DEBUG: Fallback Search. Subject: {subject}")
        
    except Exception as e:
        print(f"Keyword Extraction Global Error: {e}")
        subject = payload.query
        intent_terms = []
        
    print(f"DEBUG: Subject: {subject} | Intent: {intent_terms}")
    
    from sqlalchemy import or_, and_

    # 2a. Primary Search: strict Subject match + ANY intent match
    # If we have a clear subject, we filter chunks to MUST contain it.
    
    relevant_chunks = []
    
    if subject and len(subject) > 2:
        # Filter 1: Must contain subject (ilike)
        base_query = db.query(k_models.KnowledgeChunk).filter(k_models.KnowledgeChunk.content.ilike(f"%{subject}%"))
        
        # Filter 2: Should contain intent terms (OR)
        intent_filters = [k_models.KnowledgeChunk.content.ilike(f"%{term}%") for term in intent_terms if len(term) > 2]
        
        if intent_filters:
            # Get chunks that have Subject AND (Intent1 OR Intent2...)
            relevant_chunks = base_query.filter(or_(*intent_filters)).limit(20).all()
        else:
             relevant_chunks = base_query.limit(20).all()
             
    # Fallback if specific search failed or no subject found
    if not relevant_chunks:
        fallback_terms = [subject] + intent_terms
        filters = [k_models.KnowledgeChunk.content.ilike(f"%{t}%") for t in fallback_terms if t]
        relevant_chunks = db.query(k_models.KnowledgeChunk).filter(or_(*filters)).limit(15).all()

        
    # Search Rules (Keep simple for now)
    rule_filters = [k_models.BusinessRule.rule_description.ilike(f"%{subject}%")]
    relevant_rules = db.query(k_models.BusinessRule).filter(or_(*rule_filters)).limit(10).all()
        
    # 3. Context Construction
    hostname = os.getenv("API_PUBLIC_URL", "http://localhost:2027") # Fallback for local
    
    context_str = "RELEVANT KNOWLEDGE BASE:\n"
    seen_docs = {}
    
    for c in relevant_chunks:
        # Resolving document name and link
        if c.document_id not in seen_docs:
             doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == c.document_id).first()
             if doc:
                 seen_docs[c.document_id] = doc.filename
        
        doc_name = seen_docs.get(c.document_id, "Unknown Doc")
        # Construct Deep Link
        # Note: Frontend handles full URL, we provide relative API path or handle it there. 
        # Better to give the LLM the markdown format directly.
        # Add page number if available in metadata
        page_num = c.metadata_json.get("page_number") if c.metadata_json else None
        
        if page_num:
             # Smart Stream Link: Points to specific page streamer
             doc_link = f"/api/knowledge/documents/{c.document_id}/pages/{page_num}/stream"
        else:
             # Fallback to full download
             doc_link = f"/api/knowledge/documents/{c.document_id}/download"
        
        context_str += f"- DOC CHUNK ({doc_name}): ...{c.content[:200]}... [Link: {doc_name}]({doc_link})\n"
        
    context_str += "\nRELEVANT BUSINESS RULES:\n"
    for r in relevant_rules:
        context_str += f"- RULE: {r.rule_description} (Context: {r.trigger_context})\n"
        
    if not relevant_chunks and not relevant_rules:
        context_str = "No specific internal documents found. Answer based on general best practices."

    # 4. LLM Synthesis (DeepSeek V3)
    
    prompt = f"""
    You are 'TrainFlow-7', an expert Field Assistant.
    
    User Query: "{payload.query}"
    
    Context from Knowledge Base:
    {context_str}
    
    Instructions:
    1. Answer the user's question clearly and professionally.
    2. cite the "Reference Source" if you used a chunk or rule (e.g. "According to the Safety SOP...").
    3. **CRITICAL**: END your response with the Source PDF card on a new line. Use the exact link format provided: 
       `[{{filename}}]({{link}})`
       Example: `[Safety_Guideline.pdf](/api/knowledge/documents/12/download#page=5)`
       ENSURE NO SPACE between the brackets `]` and parenthesis `(`, e.g. `[text](link)` not `[text] (link)`.
    4. **Citation Rules**:
       - Label the link text with the Page Number if available: `[Manual.pdf (Page 5)](...)`
       - If multiple citations point to the same document/page, **DEDUPLICATE** them. Show the link only once.
       - If you have many citations for one document, try to select the 1-2 most relevant pages.
    5. If the answer is not in the context, give a helpful general answer but clarify it's general advice.
    6. Format with Markdown (bolding key terms).
    """
    
    try:
        # Use generate_text for natural language response
        final_answer = await llm.generate_text(
            prompt=prompt,
            model="x-ai/grok-4.1-fast" 
        )
        
        if not final_answer:
            final_answer = "I could not generate an answer."
        
    except Exception as e:
        print(f"DeepSeek Error: {e}")
        final_answer = "I'm having trouble connecting to the Knowledge Base right now."
        
    return {
        "answer": final_answer,
        "sources": [c.document_id for c in relevant_chunks]
    }

