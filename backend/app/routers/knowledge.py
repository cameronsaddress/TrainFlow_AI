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


# --- IN-MEMORY CACHE FOR PDF PAGE LOOKUPS ---
# Key: f"{doc_id}_{anchor_hash}" -> Value: page_number (int)
ANCHOR_PAGE_CACHE = {}

def _find_page_for_anchor(reader, anchor_text: str, doc_id: int = 0) -> int:
    """
    Helper to search for anchor text in a PDF reader object using fuzzy logic.
    Returns: 1-based physical page number, or -1 if not found.
    """
    if not anchor_text or len(anchor_text) < 3:
        return -1

    # 1. CHECK CACHE
    import hashlib
    anchor_hash = hashlib.md5(anchor_text.encode('utf-8')).hexdigest()
    cache_key = f"{doc_id}_{anchor_hash}"
    
    if cache_key in ANCHOR_PAGE_CACHE:
        print(f"DEBUG: Cache Hit for '{anchor_text}' -> Page {ANCHOR_PAGE_CACHE[cache_key]}")
        return ANCHOR_PAGE_CACHE[cache_key]
        
    print(f"Runtime Search: Scanning for '{anchor_text}'...")
    
    # Pre-compile tokens for fuzzy search
    import re
    def tokens(s): return re.findall(r'\w+', s.lower())
    
    anchor_tokens = tokens(anchor_text)
    if not anchor_tokens:
        return -1
    anchor_norm = " ".join(anchor_tokens)
    
    # Secondary simplified search (remove stopwords)
    exclude_words = {"and", "or", "the", "a", "an", "of", "in", "to", "for"}
    anchor_simple = " ".join([t for t in anchor_tokens if t not in exclude_words])

    # HEURISTIC: "Sufffix Match"
    # Titles often have "Introduction to..." prepended. 
    # Valid match if we find just the last 6 significant words.
    significant_tokens = [t for t in anchor_tokens if len(t) > 3 and t not in exclude_words]
    suffix_target = " ".join(significant_tokens[-6:]) if len(significant_tokens) > 2 else ""

    # LIMIT SCAN to first 120 pages (Performance Guard)
    scan_limit = min(len(reader.pages), 120)

    found_page = -1

    for i in range(scan_limit):
        page = reader.pages[i]
        text = page.extract_text()
        if not text: 
            continue
            
        text_lower = text.lower()
        
        # Heuristic 1: Skip obvious TOC pages
        if "table of contents" in text_lower[:500]:
            continue
        
        # Fuzzy Search Logic
        text_tokens = tokens(text_lower)
        text_norm = " ".join(text_tokens)
        
        match_found = False
        
        # 1. Exact Phrase Match
        if anchor_norm in text_norm:
            print(f"Exact Match Found on Page {i+1}")
            match_found = True
            
        # 2. Relaxed Match (if exact failed)
        elif len(anchor_simple) > 5:
             text_simple = " ".join([t for t in text_tokens if t not in exclude_words])
             if anchor_simple in text_simple:
                 print(f"Relaxed Search Match (No Stopwords): '{anchor_simple}' found on p{i+1}")
                 match_found = True

        # 3. Suffix Heuristic (New)
        elif suffix_target and len(suffix_target) > 10:
             text_simple = " ".join([t for t in text_tokens if t not in exclude_words])
             if suffix_target in text_simple:
                  print(f"Suffix Search Match ('{suffix_target}') found on p{i+1}")
                  match_found = True
        
        # 4. Aggressive Substring Match (Last Resort)
        if not match_found and len(anchor_text) > 10:
             collapsed_anchor = anchor_norm.replace(" ", "")
             collapsed_text = text_norm.replace(" ", "")
             if collapsed_anchor in collapsed_text:
                  print(f"Aggressive Collapsed Match Found on Page {i+1}")
                  match_found = True

        if match_found:
             # Check TOC heuristic (Line Level)
             valid_context = True
             for line in text_lower.split('\n'):
                 line_clean = " ".join(tokens(line))
                 if anchor_tokens[0] in line_clean: 
                     clean = line.strip()
                     # TOC check: ends with digit or "thru" or "....."
                     if clean and (clean[-1].isdigit() or clean.endswith("thru") or "..." in clean):
                         # Strict check: is this line actually the match?
                         if anchor_simple in " ".join([t for t in tokens(line) if t not in exclude_words]):
                             print(f"Skipping Page {i+1} (Detected TOC Line match: '{clean}')")
                             valid_context = False 
                             break
             
             if valid_context:
                 found_page = i + 1
                 break

    if found_page != -1:
        # Update Cache
        ANCHOR_PAGE_CACHE[cache_key] = found_page
        return found_page

    return -1

@router.post("/documents/{doc_id}/locate")
async def locate_document_page(
    doc_id: int, 
    payload: dict, # {"anchor_text": "str"}
    db: Session = Depends(get_db)
):
    """
    Returns the physical page number for a given anchor text.
    """
    anchor_text = payload.get("anchor_text")
    if not anchor_text:
        return {"found": False, "page": None}

    doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, "Document file not found")
        
    try:
        from pypdf import PdfReader
        reader = PdfReader(doc.file_path)
        found_page = _find_page_for_anchor(reader, anchor_text, doc_id)
        
        if found_page != -1:
            return {"found": True, "page": found_page}
        else:
             return {"found": False, "page": None}
             
    except Exception as e:
        print(f"Locate Error: {e}")
        return {"found": False, "page": None, "error": str(e)}


@router.get("/documents/{doc_id}/pages/{page_num}/stream")
async def stream_document_page(
    doc_id: int, 
    page_num: int, 
    anchor_text: str = None, # Optional: Text to search for
    db: Session = Depends(get_db)
):
    """
    Smart Stream: Extracts ONLY the requested page (+/- context optional) 
    and streams it as a lightweight PDF.
    """
    doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, "Document file not found")

    try:
        from pydantic import BaseModel
        from pypdf import PdfReader, PdfWriter
        from io import BytesIO
        from fastapi.responses import StreamingResponse
        from fastapi.concurrency import run_in_threadpool

        # Offload heavy PDF processing to threadpool
        def process_pdf_sync():
            reader = PdfReader(doc.file_path)
            total_pages = len(reader.pages)
            
            # --- Runtime Search Override ---
            target_page = page_num
            if anchor_text and len(anchor_text) > 3:
                # Pass doc.id for caching
                found_page = _find_page_for_anchor(reader, anchor_text, doc.id)
                if found_page != -1:
                    target_page = found_page
                    print(f"Runtime Search Success: Found on Physical Page {target_page}")
                else:
                    print(f"Runtime Search Failed: '{anchor_text}' not found. Fallback to Page {target_page}")
            
            if target_page < 1: target_page = 1
            if target_page > total_pages: target_page = 1
                 
            writer = PdfWriter()
            
            # 0-indexed adjustment
            target_idx = target_page - 1
            
            # Context Buffer: Starts at target, +10 pages forward
            start_idx = target_idx
            end_idx = min(total_pages, target_idx + 10) # slice is exclusive at end
            
            # Add pages in range
            for i in range(start_idx, end_idx):
                writer.add_page(reader.pages[i])
            
            output_stream = BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)
            
            # Sanitize filename for headers
            safe_filename = doc.filename.replace(" ", "_").replace('"', '')
            
            return output_stream, safe_filename, target_page

        # Execute in threadpool
        output_stream, safe_filename, final_page_num = await run_in_threadpool(process_pdf_sync)
        
        return StreamingResponse(
            output_stream, 
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{safe_filename}_p{final_page_num}.pdf"'}
        )
        
    except Exception as e:
        print(f"Smart Stream Error: {e}")
        # Fallback to full file if slicing fails
        from fastapi.responses import FileResponse
        # Sanitize filename for fallback too
        safe_filename = doc.filename.replace(" ", "_").replace('"', '')
        return FileResponse(
            doc.file_path, 
            filename=safe_filename, 
            media_type="application/pdf", 
            content_disposition_type="inline"
        )

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

