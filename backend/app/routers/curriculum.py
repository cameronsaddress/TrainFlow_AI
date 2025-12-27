from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Header
from fastapi.responses import StreamingResponse
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

# --- YOUTUBE INGESTION ---
from pydantic import BaseModel

class YoutubeIngestRequest(BaseModel):
    url: str

@router.post("/ingest_youtube")
async def ingest_youtube(
    payload: YoutubeIngestRequest,
    background_tasks: BackgroundTasks
):
    """
    Queue a YouTube video for download and ingestion.
    Returns immediately with a 'queued' status.
    """
    url = payload.url
    
    # Define Worker Function
    def process_youtube_download(target_url: str):
        # We need a NEW DB Session because the Dependency one is closed after response
        from ..db import SessionLocal
        local_db = SessionLocal()
        import yt_dlp
        
        try:
            print(f"[YoutubeWorker] Starting download for: {target_url}")
            ydl_opts = {
                'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[ext=mp4]',
                'outtmpl': os.path.join(DATA_DIR, '%(title)s.%(ext)s'),
                'restrictfilenames': True,
                'noplaylist': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                },
            }
            
            filename = None
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=True)
                filename = ydl.prepare_filename(info)
            
            if filename and os.path.exists(filename):
                final_filename = os.path.basename(filename)
                
                # Check for duplicate
                existing = local_db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename == final_filename).first()
                if existing:
                    if existing.is_archived:
                        print(f"[YoutubeWorker] Found Archived Duplicate: {final_filename}. Unarchiving...")
                        existing.is_archived = False
                        local_db.commit()
                        # We don't need to re-download or re-ingest if it's already there.
                        # But if you want to re-process, we could, but let's just restore it for now.
                    else:
                        print(f"[YoutubeWorker] Skipping active duplicate: {final_filename}")
                    
                    local_db.close()
                    return

                # Create DB Entry
                video = k_models.VideoCorpus(
                    filename=final_filename,
                    file_path=filename,
                    status=k_models.DocStatus.PENDING
                )
                local_db.add(video)
                local_db.commit()
                local_db.refresh(video)
                
                # Trigger Ingestion
                import redis
                REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
                try:
                    r = redis.from_url(REDIS_URL)
                    r.publish("corpus_jobs", str(video.id))
                    print(f"[YoutubeWorker] Queued ingestion for {video.id}")
                except Exception as e:
                    print(f"[YoutubeWorker] Redis Error: {e}")
            else:
                print(f"[YoutubeWorker] Download failed or file missing for {target_url}")

        except Exception as e:
            print(f"[YoutubeWorker] Error processing {target_url}: {e}")
        finally:
            local_db.close()

    # Dispatch to Background
    background_tasks.add_task(process_youtube_download, url)
    
    return {"status": "queued", "message": "Download started in background"}

@router.get("/videos")
async def list_videos(include_archived: bool = False, db: Session = Depends(get_db)):
    """List active video corpus items (exclude archived by default)."""
    query = db.query(k_models.VideoCorpus).options(
        defer(k_models.VideoCorpus.transcript_text),
        defer(k_models.VideoCorpus.transcript_json),
        defer(k_models.VideoCorpus.ocr_text),
        defer(k_models.VideoCorpus.ocr_json)
    )
    
    if not include_archived:
        query = query.filter(k_models.VideoCorpus.is_archived == False)
        
    return query.order_by(k_models.VideoCorpus.created_at.desc()).all()

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

    return {"status": "deleted"}

@router.post("/archive_all_corpus")
async def archive_all_corpus(db: Session = Depends(get_db)):
    """
    Mark all current videos as 'Archived'.
    They will no longer be used for new Curriculum generation, 
    but remain in the database/disk for reference.
    """
    count = db.query(k_models.VideoCorpus).filter(
        k_models.VideoCorpus.is_archived == False
    ).update({k_models.VideoCorpus.is_archived: True})
    
    db.commit()
    return {"status": "archived", "count": count}

@router.post("/generate_structure")
async def generate_structure_endpoint(db: Session = Depends(get_db)):
    """Trigger the 'Top-Level' logic: Curriculum Architect (Streaming)."""
    
    from ..services import curriculum_architect
    import json

    async def event_generator():
        try:
            # Singleton Logic: Purge previous courses to "Overwrite"
            # UPDATE: Multi-Course Support Enabled. Do NOT delete previous plans.
            # db.query(k_models.TrainingCurriculum).delete()
            # db.commit()
            
            # Iterate the service generator (Async)
            generator = curriculum_architect.generate_curriculum(db)
            
            async for item in generator:
                if isinstance(item, str):
                    # Status Update
                    yield json.dumps({"type": "status", "msg": item}) + "\n"
                elif isinstance(item, dict):
                    # Final Result
                    print("DEBUG: Router received Dict from Generator. Saving...", flush=True)
                    try:
                        # Ensure we persist it
                        # DEDUPLICATION LOGIC: Check if course exists by title
                        existing_plan = db.query(k_models.TrainingCurriculum).filter(
                            k_models.TrainingCurriculum.title == item.get("course_title")
                        ).first()

                        if existing_plan:
                            print(f"DEBUG: Found existing course '{existing_plan.title}' (ID {existing_plan.id}). Updating...", flush=True)
                            existing_plan.structured_json = item
                            # Force update for JSON field
                            from sqlalchemy.orm.attributes import flag_modified
                            flag_modified(existing_plan, "structured_json")
                            db.commit()
                            db.refresh(existing_plan)
                            new_plan = existing_plan # for downstream ref
                        else:
                            new_plan = k_models.TrainingCurriculum(
                                title=item.get("course_title", "Untitled Course"),
                                structured_json=item
                            )
                            db.add(new_plan)
                            db.commit()
                            db.refresh(new_plan)
                            print(f"DEBUG: Saved NEW Curriculum ID {new_plan.id}", flush=True)
                        
                        # POST-GENERATION: Auto-Archive used videos to "Clear the Queue"
                        updated_count = db.query(k_models.VideoCorpus).filter(
                            k_models.VideoCorpus.status == k_models.DocStatus.READY,
                            k_models.VideoCorpus.is_archived == False
                        ).update({k_models.VideoCorpus.is_archived: True})
                        db.commit()
                        print(f"DEBUG: Auto-Archived {updated_count} videos to clear the queue.", flush=True)
                        
                        result_payload = {
                            "id": new_plan.id,
                            "title": new_plan.title,
                            "modules_count": len(item.get("modules", []))
                        }
                        
                        yield json.dumps({"type": "result", "payload": result_payload}) + "\n"
                        break
                    except Exception as e:
                        print(f"CRITICAL: Failed to save Curriculum to DB: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        yield json.dumps({"type": "error", "msg": f"DB Save Failed: {str(e)}"}) + "\n"
                
        except Exception as e:
            print(f"Error generating structure: {e}", flush=True)
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "msg": str(e)}) + "\n"
            yield json.dumps({"type": "error", "msg": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
@router.get("/plans")
async def list_curricula(db: Session = Depends(get_db)):
    return db.query(k_models.TrainingCurriculum).order_by(k_models.TrainingCurriculum.created_at.desc()).all()

@router.get("/plans/{plan_id}")
async def get_curriculum(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(k_models.TrainingCurriculum).filter(k_models.TrainingCurriculum.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Curriculum Plan not found")
        
    # OPTIMIZATION: "Smart Load"
    # 1. Extract required filenames to filter the query
    required_filenames = set()
    if plan.structured_json and isinstance(plan.structured_json, dict) and "modules" in plan.structured_json:
        for mod in plan.structured_json.get("modules", []):
             # 1. Module level recommendations
             if "recommended_source_videos" in mod:
                 for vid in mod["recommended_source_videos"]:
                     if vid: required_filenames.add(vid)
             
             # 2. Lesson clips
             if "lessons" in mod:
                 for lesson in mod["lessons"]:
                     if "source_clips" in lesson:
                         for clip in lesson["source_clips"]:
                             if "video_filename" in clip and clip["video_filename"]:
                                 required_filenames.add(clip["video_filename"])

    # 2. Query only required videos AND defer heavy text fields
    videos = []
    if required_filenames:
        videos = db.query(k_models.VideoCorpus).filter(
            k_models.VideoCorpus.filename.in_(list(required_filenames))
        ).options(
            defer(k_models.VideoCorpus.transcript_text),
            defer(k_models.VideoCorpus.transcript_json),
            defer(k_models.VideoCorpus.ocr_text),
            defer(k_models.VideoCorpus.ocr_json)
        ).all()

    file_map = {}
    for v in videos:
        # We serve from /data/corpus/{os.path.basename(v.file_path)}
        if v.file_path:
             storage_filename = os.path.basename(v.file_path)
             file_map[v.filename] = storage_filename
             
    # Return hybrid object
    return {
        "id": plan.id,
        "title": plan.title,
        "structured_json": plan.structured_json,
        "created_at": plan.created_at,
        "file_map": file_map # Frontend will use this lookup
    }

from pydantic import BaseModel
from typing import Dict, Any, List

class CurriculumUpdateSchema(BaseModel):
    title: str
    structured_json: Dict[str, Any]

@router.put("/plans/{plan_id}")
async def update_curriculum(plan_id: int, payload: CurriculumUpdateSchema, db: Session = Depends(get_db)):
    """Update curriculum structure (Visual Editor save)."""
    plan = db.query(k_models.TrainingCurriculum).filter(k_models.TrainingCurriculum.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Curriculum Plan not found")
        
    # Update Fields
    plan.title = payload.title
    # Sanitize or Validate if needed (for now transparent pass-through)
    plan.structured_json = payload.structured_json
    
    db.commit()
    db.refresh(plan)
    return {"status": "updated", "id": plan.id}

@router.get("/stream/{filename}")
async def stream_video(
    filename: str, 
    range: str = Header(None),
    start: float = None,
    end: float = None
):
    """
    Stream video.
    If 'start' and 'end' are provided:
    - Use ffmpeg to slice the video on the fly (backend slicing).
    - Returns a distinct MP4 stream of just that segment.
    - Ignores 'Range' header for simplicity in this mode (browser sees full 'sliced' file).
    
    If no params:
    - Standard static file streaming with Range support.
    """
    # 1. Locate file (UUID or Friendly Name)
    SAFE_FILENAME = os.path.basename(filename)
    file_path = f"/app/data/corpus/{SAFE_FILENAME}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")

    # MODE A: Server-Side Slicing (FFmpeg)
    if start is not None and end is not None:
        duration = end - start
        if duration <= 0:
            raise HTTPException(status_code=400, detail="Invalid duration")
            
        # print(f"DEBUG: Slicing {filename} | Start: {start} | End: {end} | Duration: {duration}")
        
        # Use /dev/shm for fast RAM-based temp storage
        import uuid
        temp_filename = f"slice_{uuid.uuid4()}.mp4"
        temp_path = os.path.join("/dev/shm", temp_filename)
        
        # Ensure /dev/shm exists
        if not os.path.exists("/dev/shm"):
            temp_path = os.path.join("/tmp", temp_filename)

        # cmd: ffmpeg -ss {start} -i {input} -t {duration} -c copy -movflags faststart -y {output}
        cmd = [
            "ffmpeg",
            "-ss", str(float(start)),
            "-i", file_path,
            "-t", str(float(duration)),
            "-c", "copy",
            "-movflags", "faststart",
            "-y",
            temp_path
        ]
        
        import subprocess
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
             print(f"FFmpeg Slicing Error: {e}")
             raise HTTPException(status_code=500, detail="Video slicing failed")

        # Serve file, delete after sending
        def cleanup():
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        background_task = BackgroundTasks()
        background_task.add_task(cleanup)
        
        from fastapi.responses import FileResponse
        return FileResponse(
            temp_path, 
            media_type="video/mp4", 
            filename=f"clip_{start}_{end}.mp4",
            background=background_task
        )

    # MODE B: Full File Static Streaming (with Range support)
    file_size = os.path.getsize(file_path)
    
    # Handle Range Header
    start_byte = 0
    end_byte = file_size - 1
    
    if range:
        try:
            s_str, e_str = range.replace("bytes=", "").split("-")
            start_byte = int(s_str)
            if e_str:
                end_byte = int(e_str)
        except ValueError:
            pass 
            
    if end_byte >= file_size:
        end_byte = file_size - 1
    if start_byte >= file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")

    chunk_size = (end_byte - start_byte) + 1
    
    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start_byte)
            bytes_to_read = chunk_size
            while bytes_to_read > 0:
                chunk = f.read(min(1024*64, bytes_to_read))
                if not chunk:
                    break
                bytes_to_read -= len(chunk)
                yield chunk
                
    headers = {
        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4",
    }
    
    return StreamingResponse(iterfile(), status_code=206, headers=headers)

@router.get("/stream")
async def stream_video(
    filename: str, 
    range: str = Header(None),
    start: float = None,
    end: float = None,
    db: Session = Depends(get_db)
):
    """
    Stream video via Query Param.
    /stream?filename=Day%201.mp4&start=30&end=60
    """
    print(f"DEBUG: Streaming Request (Query). Filename: '{filename}' | Start: {start} | End: {end}")
    
    # 1. Resolve Path via DB
    # Try finding by exact filename (FastAPI decodes query params)
    decoded_filename = filename 
    video = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename == decoded_filename).first()

    # --- FUZZY MATCHING LOGIC ---
    if not video:
        # A. Try replacing spaces with underscores (and vice versa)
        # "Day 1.mp4" <-> "Day_1.mp4"
        if " " in decoded_filename:
            alt_name = decoded_filename.replace(" ", "_")
        else:
            alt_name = decoded_filename.replace("_", " ")
            
        print(f"DEBUG: Exact Match Miss. Trying Alt: '{alt_name}'")
        video = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename == alt_name).first()

    if not video:
        # B. Case-Insensitive Search (Postgres ILIKE behavior using func.lower)
        from sqlalchemy import func
        print(f"DEBUG: Exact/Alt Miss. Trying Case-Insensitive for '{decoded_filename}'")
        video = db.query(k_models.VideoCorpus).filter(func.lower(k_models.VideoCorpus.filename) == decoded_filename.lower()).first()
        
    if not video:
        # C. Regex/Partial Match (Last Resort: Contains & normalized)
        # Try finding a video that *contains* the core name structure
        # Heuristic: strip extension, strip non-alphanumeric, look for match
        import re
        core_name = re.sub(r'[^a-zA-Z0-9]', '', os.path.splitext(decoded_filename)[0].lower())
        
        # This is expensive, so we do it in Python for the small corpus (usually < 1000 items)
        # If corpus > 10k, use pg_trgm or similar.
        print(f"DEBUG: Deep Fuzzy Search for core signature: '{core_name}'")
        all_videos = db.query(k_models.VideoCorpus).all()
        for v in all_videos:
            v_core = re.sub(r'[^a-zA-Z0-9]', '', os.path.splitext(v.filename)[0].lower())
            if core_name in v_core or v_core in core_name:
                video = v
                print(f"DEBUG: Fuzzy Match Found! '{decoded_filename}' -> '{v.filename}'")
                break

    file_path = None
    if video and video.file_path:
        if os.path.exists(video.file_path):
            file_path = video.file_path
            print(f"DEBUG: Found via DB/Fuzzy: {file_path}")
        else:
            print(f"DEBUG: DB Record Found but File Missing: {video.file_path}")

    if not file_path:
        # Fallback: Maybe it IS the UUID (or simple filename)?
        SAFE_FILENAME = os.path.basename(decoded_filename)
        fallback_path = f"/app/data/corpus/{SAFE_FILENAME}"
        if os.path.exists(fallback_path):
            file_path = fallback_path
            print(f"DEBUG: Found via Direct Path Fallback: {file_path}")
        else:
            # Try alternate fallback (swapped spaces/underscores)
            if " " in SAFE_FILENAME:
                alt = SAFE_FILENAME.replace(" ", "_")
            else:
                alt = SAFE_FILENAME.replace("_", " ")
            
            fallback_path_alt = f"/app/data/corpus/{alt}"
            if os.path.exists(fallback_path_alt):
                 file_path = fallback_path_alt
                 print(f"DEBUG: Found via Direct Path Fallback (Alt): {file_path}")

    if not file_path:
        print(f"DEBUG: 404 Not Found for {decoded_filename} (and fuzzy variants)")
        raise HTTPException(status_code=404, detail=f"Video not found: {decoded_filename}")

    # MODE A: Server-Side Slicing (FFmpeg)
    if start is not None and end is not None:
        duration = end - start
        if duration <= 0:
            raise HTTPException(status_code=400, detail="Invalid duration")
            
        print(f"DEBUG: Slicing {filename} | Start: {start} | End: {end} | Duration: {duration}")
        
        # Use disk-based storage for large clips to avoid /dev/shm (64MB) limits
        import uuid
        temp_dir = "/app/data/temp_slices"
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_filename = f"slice_{uuid.uuid4()}.mp4"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # cmd: ffmpeg -ss {start} -i {input} -t {duration} -c copy -movflags faststart -y {output}
        cmd = [
            "ffmpeg",
            "-ss", str(start),
            "-i", file_path,
            "-t", str(duration),
            "-c", "copy",
            "-movflags", "faststart",
            "-y",
            temp_path
        ]
        
        import subprocess
        # Run blocking (fast for stream copy)
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) # Capture stderr
        except subprocess.CalledProcessError as e:
             # Decode and print error
             error_log = e.stderr.decode() if e.stderr else "No stderr captured"
             print(f"FFmpeg Slicing Error: {error_log}")
             raise HTTPException(status_code=500, detail=f"Video slicing failed: {error_log}")

        # Serve file, delete after sending
        def cleanup():
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        background_task = BackgroundTasks()
        background_task.add_task(cleanup)
        
        from fastapi.responses import FileResponse
        return FileResponse(
            temp_path, 
            media_type="video/mp4", 
            filename=f"clip_{start}_{end}.mp4",
            background=background_task
        )

    # MODE B: Full File Static Streaming (with Range support)
    file_size = os.path.getsize(file_path)
    
    # Handle Range Header
    start_byte = 0
    end_byte = file_size - 1
    
    if range:
        try:
            # Parse 'bytes=0-1024'
            s_str, e_str = range.replace("bytes=", "").split("-")
            start_byte = int(s_str)
            if e_str:
                end_byte = int(e_str)
        except ValueError:
            pass 
            
    if end_byte >= file_size:
        end_byte = file_size - 1
    if start_byte >= file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")

    chunk_size = (end_byte - start_byte) + 1
    
    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start_byte)
            bytes_to_read = chunk_size
            while bytes_to_read > 0:
                chunk = f.read(min(1024*64, bytes_to_read))
                if not chunk:
                    break
                bytes_to_read -= len(chunk)
                yield chunk
                
    headers = {
        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4",
    }
    
    return StreamingResponse(iterfile(), status_code=206, headers=headers)
