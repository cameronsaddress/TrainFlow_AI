from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, defer
from ..db import get_db
from ..models import knowledge as k_models
from ..services import corpus_ingestor
import shutil
import os
import uuid

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

DATA_DIR = "/app/data/corpus"
os.makedirs(DATA_DIR, exist_ok=True)

@router.post("/ingest_video")
async def ingest_video(
    file: UploadFile = File(...), 
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Upload a Video for Global Context Indexing (ASR + OCR).
    Bypasses the "Fusion Engine" logic.
    """
    # 1. Save File
    file_ext = os.path.splitext(file.filename)[1]
    if file_ext.lower() not in [".mp4", ".mov", ".avi"]:
        raise HTTPException(400, "Only Video files supported")

    new_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(DATA_DIR, new_filename)
    
    # 1. Save File (Non-blocking)
    # Use threadpool for I/O to avoid blocking async event loop
    from fastapi.concurrency import run_in_threadpool
    def save_file_sync():
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    await run_in_threadpool(save_file_sync)
        
    # 2. Create DB Entry
    video = k_models.VideoCorpus(
        filename=file.filename,
        file_path=file_path,
        status=k_models.DocStatus.PENDING
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    
    # 3. Trigger Ingestion (via Redis / Worker)
    import redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        r = redis.from_url(REDIS_URL)
        r.publish("corpus_jobs", str(video.id))
    except Exception as e:
        print(f"CRITICAL: Failed to trigger corpus job for {video.id}: {e}")
        # Update status to FAILED so it doesn't look stuck
        video.status = k_models.DocStatus.FAILED
        video.error_message = f"Dispatch Error: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to queue ingestion job.")
    
    return {"status": "uploaded", "id": video.id, "filename": video.filename}

@router.get("/videos")
async def list_videos(db: Session = Depends(get_db)):
    """List all indexed video corpus items."""
    return db.query(k_models.VideoCorpus).options(
        defer(k_models.VideoCorpus.transcript_text),
        defer(k_models.VideoCorpus.transcript_json),
        defer(k_models.VideoCorpus.ocr_text),
        defer(k_models.VideoCorpus.ocr_json)
    ).order_by(k_models.VideoCorpus.created_at.desc()).all()

@router.delete("/videos/{video_id}")
async def delete_video(video_id: int, db: Session = Depends(get_db)):
    """Delete a video corpus item."""
    video = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
        
    if video.file_path and os.path.exists(video.file_path):
        os.remove(video.file_path)
        
    db.delete(video)
    db.commit()
    return {"status": "deleted"}

@router.post("/generate_structure")
async def generate_structure_endpoint(db: Session = Depends(get_db)):
    """Trigger the 'Top-Level' logic: Curriculum Architect."""
    # This might take 30-60s for LLM generation. 
    # For MVP we can await it. For Prod, use background tasks.
    # Given 128k context, it might be 60s+.
    
    from ..services import curriculum_architect

    try:
        # Changed to return dict with ID
        result = curriculum_architect.generate_curriculum(db)
        if "error" in result:
             raise HTTPException(status_code=400, detail=result["error"])
        return result 
    except Exception as e:
        print(f"Error generating structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plans")
async def list_curricula(db: Session = Depends(get_db)):
    return db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).all()

@router.get("/plans/{plan_id}")
async def get_curriculum(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(k_models.TrainingCurriculum).filter(k_models.TrainingCurriculum.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Curriculum Plan not found")
    return plan
