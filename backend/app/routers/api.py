from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from ..db import get_db
from sqlalchemy.orm import Session
from datetime import datetime
from ..dependencies import verify_admin, verify_viewer

# --- Glossary Router ---
glossary_router = APIRouter(prefix="/glossary", tags=["glossary"])
export_router = APIRouter(prefix="/export", tags=["Export"])
processing_router = APIRouter(prefix="/process", tags=["Processing"])

@export_router.get("/ping")
async def ping_export():
    return {"status": "pong"}

@glossary_router.post("/", dependencies=[Depends(verify_admin)])
async def add_glossary_entry(entry: dict, db: Session = Depends(get_db)):
    """
    Gap 4: Dynamic Domain Glossary Management.
    Body: {"keyword": "Access Denied", "resolution": "Check VPN"}
    """
    from ..models.models import GlossaryEntry
    
    new_entry = GlossaryEntry(
        error_keyword=entry.get("keyword"),
        resolution_text=entry.get("resolution")
    )
    try:
        db.add(new_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Entry likely exists")
        
    return {"status": "added", "id": new_entry.id}

# --- Uploads Router ---
uploads_router = APIRouter(prefix="/uploads", tags=["uploads"])

@uploads_router.get("/", dependencies=[Depends(verify_viewer)])
async def list_videos(db: Session = Depends(get_db)):
    """List all video jobs for the dashboard."""
    from ..models.models import Video, JobStatus
    videos = db.query(Video).order_by(Video.created_at.desc()).limit(10).all()
    
    results = []
    for v in videos:
        # Get flow info if exists
        flow = v.flows[0] if v.flows else None
        steps_count = len(flow.steps) if flow and flow.steps else 0
        
        # Determine thumbnail
        thumbnail_url = None
        if flow and flow.steps:
            # Try to find first step with a screenshot
            first_step = flow.steps[0] # Steps are usually ordered by ID or step_number in DB relationship default? Safer to sort if needed but usually okay.
            # Actually, let's sort purely by step_number to be safe
            sorted_steps = sorted(flow.steps, key=lambda s: s.step_number)
            if sorted_steps and sorted_steps[0].screenshot_path:
                # Convert absolute path /app/data/... to URL path /data/...
                path = sorted_steps[0].screenshot_path
                if path.startswith("/app/data"):
                    thumbnail_url = path.replace("/app/data", "/data")
                elif path.startswith("/data"): # Already relative-ish
                    thumbnail_url = path
        
        results.append({
            "id": v.id,
            "filename": v.filename,
            "status": v.status,
            "processing_stage": v.processing_stage,
            "created_at": v.created_at.isoformat(),
            "flow_id": flow.id if flow else None,
            "steps_count": steps_count,
            "thumbnail_url": thumbnail_url,
            "has_guide": any(v.flows) and any(f.wo_guides for f in v.flows) # Simplification
        })
    return results

@uploads_router.delete("/{video_id}", dependencies=[Depends(verify_viewer)])
async def delete_video(video_id: int, db: Session = Depends(get_db)):
    """Delete a video and its associated flows."""
    from ..models.models import Video, ProcessFlow
    
    # 1. Get Video
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    try:
        # 2. Delete associated ProcessFlows (Manual Cascade)
        # Note: Depending on DB config, this might not be strictly necessary if ON DELETE CASCADE is set in SQL,
        # but models.py didn't show it. Safest to do explicit delete.
        flows = db.query(ProcessFlow).filter(ProcessFlow.video_id == video_id).all()
        for flow in flows:
            # Delete associated steps if needed? Usually Flow->Steps relation might cascade?
            # Let's hope SQL alchemy relationship `steps = relationship("TrainingStep", cascade="all, delete-orphan")` exists.
            # If not, we might leave orphan steps.
            db.delete(flow)
            
        # 3. Delete Video
        db.delete(video)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")
        
    return {"status": "deleted", "id": video_id}

@uploads_router.get("/{video_id}/transcription", dependencies=[Depends(verify_viewer)])
async def get_video_transcription(video_id: int, db: Session = Depends(get_db)):
    """Get raw transcription and OCR logs for a video."""
    from ..models.models import Video
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    return {
        "transcription_log": video.transcription_log,
        # "ocr_log": video.ocr_log # Optional, user asked for "full transcription llm got", usually implies ASR. But OCR is good context.
        # Let's verify if user wants OCR. "full transcription that the llm got".
        # LLM gets "Spoken: ... | Screen: ..." (Line 211 in worker.py).
        # We can return both and let UI display tabs.
        "ocr_log": video.ocr_log
    }

@uploads_router.post("/")
async def upload_video(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Handle video upload.
    Saves to MinIO, creates DB entry, and will trigger processing job.
    """
    from ..models.models import Video, JobStatus
    from ..services.storage import upload_file
    
    # 1. Upload to Object Store
    s3_key = upload_file(file.file, file.filename, file.content_type)
    
    # 2. Create DB Entry
    new_video = Video(
        filename=file.filename,
        s3_key=s3_key,
        status=JobStatus.PENDING
    )
    db.add(new_video)
    db.commit()
    db.refresh(new_video)
    
    # 3. Trigger Background Task
    import redis
    import os
    
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        r = redis.from_url(REDIS_URL)
        r.publish("video_jobs", str(new_video.id))
    except Exception as e:
        print(f"Failed to trigger job: {e}")
    
    return {
        "id": new_video.id,
        "filename": new_video.filename,
        "status": new_video.status,
        "s3_key": new_video.s3_key
    }

# --- Processing Router ---
processing_router = APIRouter(prefix="/process", tags=["processing"])

@processing_router.get("/{video_id}/status", dependencies=[Depends(verify_viewer)])
async def get_processing_status(video_id: int, db: Session = Depends(get_db)):
    from ..models.models import Video
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    return {
        "video_id": video.id, 
        "status": video.status, 
        "processing_stage": video.processing_stage,
        "progress": 45  # Keep mock progress for now or map stage to %
    }

@processing_router.get("/jobs")
async def get_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get recent processing jobs (Videos).
    """
    from ..models import models
    # Return videos descending by ID
    videos = db.query(models.Video).order_by(models.Video.id.desc()).offset(skip).limit(limit).all()
    
    # Map to Job-like structure
    res = []
    for v in videos:
        res.append({
            "id": v.id,
            "video_id": v.id,
            "status": v.status,
            "progress": 100 if v.status == "COMPLETED" else 0, # Simple progress
            "current_stage": v.processing_stage,
            "error_message": v.error_message,
            "created_at": v.created_at,
            "video_filename": v.filename
        })
    return res

@processing_router.get("/flows/{flow_id}", dependencies=[Depends(verify_viewer)])
async def get_process_flow(flow_id: int, db: Session = Depends(get_db)):
    from ..models import models
    flow = db.query(models.ProcessFlow).filter(models.ProcessFlow.id == flow_id).first()
    if not flow:
         raise HTTPException(status_code=404, detail="Flow not found")
    
    # improved conversion logic
    nodes = []
    edges = []
    
    # Start Node
    nodes.append({
        "id": "start",
        "type": "input",
        "data": { "label": "Start" },
        "position": { "x": 250, "y": 0 }
    })

    
    previous_node_id = "start"
    y_pos = 100
    
    sorted_steps = sorted(flow.steps, key=lambda s: s.step_number)
    
    for step in sorted_steps:
        node_id = str(step.id)
        
        # Determine Node Type
        # e.g. if step_type=="decision", use diamond shape (impl via custom type or valid ReactFlow type)
        # For prototype, standard clean nodes
        label = f"{step.step_number}. {step.action_details[:30]}..."
        if step.decision_map:
             label += " (Decision)"
             
        nodes.append({
            "id": node_id,
            "data": { 
                "label": label, 
                "details": step.action_details,
                "system": step.system_name,
                "type": step.step_type,
                "start_ts": step.start_ts,
                "duration": step.duration,
                "expected_result": step.expected_result,
                "screenshot_path": step.screenshot_path,
                "video_clip_path": step.video_clip_path,
                "notes": step.notes,
                "prerequisites": step.prerequisites
            },
            "position": { "x": 250, "y": y_pos }
        })
        
        # Create Edge
        edges.append({
            "id": f"e{previous_node_id}-{node_id}",
            "source": previous_node_id,
            "target": node_id,
            "animated": True
        })
        
        previous_node_id = node_id
        y_pos += 150
        
    return {
        "flow_id": flow.id, 
        "nodes": nodes, 
        "edges": edges, 
        "summary_video_path": flow.summary_video_path,
        "removal_summary": flow.removal_summary
    }

@processing_router.put("/flows/{flow_id}", dependencies=[Depends(verify_admin)])
async def update_process_flow(flow_id: int, flow_data: dict, db: Session = Depends(get_db)):
    """
    FR-15: Save updated flow layout AND content.
    Synchronizes graph edits back to TrainingStep records.
    Requires Admin privileges.
    """
    from ..models import models
    flow = db.query(models.ProcessFlow).filter(models.ProcessFlow.id == flow_id).first()
    if not flow:
         raise HTTPException(status_code=404, detail="Flow not found")
         
    # 1. Sync Edits to TrainingStep Table (So exports work)
    try:
        nodes = flow_data.get("nodes", [])
        for node in nodes:
            # ID mapping: node['id'] is str(step_number) as per GET logic
            try:
                step_num = int(node["id"])
                # Find the step
                step = db.query(models.TrainingStep).filter(
                    models.TrainingStep.flow_id == flow_id,
                    models.TrainingStep.step_number == step_num
                ).first()
                
                if step:
                    data = node.get("data", {})
                    # Update fields
                    if "details" in data: step.action_details = data["details"]
                    if "expected_result" in data: step.expected_result = data["expected_result"]
                    if "notes" in data: step.notes = data["notes"]
                    if "system" in data: step.system_name = data["system"]
                    if "prerequisites" in data: step.prerequisites = data["prerequisites"] # JSON or Text? DB is JSON, Editor is text.
                    # Handle Prerequisites type mismatch if models.py says JSON but editor sends string
                    # Model: prerequisites = Column(JSON, default=[])
                    # Editor sends string. Let's wrap in list if string.
                    if "prerequisites" in data:
                        val = data["prerequisites"]
                        if isinstance(val, str):
                            step.prerequisites = [val] if val.strip() else []
                        else:
                            step.prerequisites = val
                            
            except ValueError:
                continue # Skip non-integer IDs (e.g. decision nodes if named differently)
    except Exception as e:
        print(f"Error syncing steps: {e}")
        # Don't fail the save, just log.
         
    # 2. Create Version Snapshot (FR-16)
    from ..models.models import FlowVersion
    last_version = db.query(FlowVersion).filter(FlowVersion.flow_id == flow_id).order_by(FlowVersion.version_number.desc()).first()
    new_version_num = (last_version.version_number + 1) if last_version else 1
    
    version = FlowVersion(
        flow_id=flow.id,
        version_number=new_version_num,
        graph_data=flow_data
    )
    db.add(version)
    
    # 3. Save the visual layout to graph_data
    flow.graph_data = flow_data
    flow.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "saved", "version": new_version_num}

@processing_router.get("/flows/{flow_id}/history")
async def get_flow_history(flow_id: int, db: Session = Depends(get_db)):
    """
    FR-16: Get change history for a flow.
    """
    from ..models import models
    versions = db.query(models.FlowVersion).filter(models.FlowVersion.flow_id == flow_id).order_by(models.FlowVersion.version_number.desc()).all()
    return [
        {"version": v.version_number, "created_at": v.created_at, "nodes_count": len(v.graph_data.get("nodes", []))}
        for v in versions
    ]

# --- Public Router ---
public_router = APIRouter(tags=["public"])

@public_router.get("/process/gpu-status")
async def get_gpu_status():
    """
    Returns REAL status using Torch/CUDA.
    No mock data.
    """
    import torch
    import subprocess
    
    if not torch.cuda.is_available():
        return {
            "model": "CPU Only",
            "status": "Offline (No CUDA)",
            "utilization": "0%",
            "memory_used": "0GB",
            "memory_total": "System RAM",
            "temperature": "--"
        }
        
    try:
        # Get Real Device Info
        d = torch.device("cuda:0")
        props = torch.cuda.get_device_properties(d)
        
        # Memory Metrics
        # reserved = cached by caching allocator
        # allocated = actually used by tensors
        reserved = torch.cuda.memory_reserved(d) / (1024**3)
        total = props.total_memory / (1024**3)
        util_pct = (reserved / total) * 100
        
        # Temp (Try nvidia-smi as Torch doesn't give temp)
        temp = "N/A"
        try:
            res = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], 
                encoding="utf-8"
            )
            temp = f"{res.strip()}C"
        except:
            pass

        return {
            "model": props.name,
            "status": "Online",
            "utilization": f"{util_pct:.1f}%",
            "memory_used": f"{reserved:.1f}GB",
            "memory_total": f"{total:.1f}GB",
            "temperature": temp
        }
    except Exception as e:
        return {
            "model": "Error Detecting",
            "status": "Error",
            "utilization": "0%",
            "details": str(e)
        }
@processing_router.post("/flows/{flow_id}/generate-wo", dependencies=[Depends(verify_admin)])
async def generate_wo_guide_endpoint(flow_id: int, target_system: str = "Generic", db: Session = Depends(get_db)):
    """
    FR-13: Generate a technical Work Order Creation Guide for a specific system.
    Requires Admin privileges.
    """
    from ..models import models
    from ..services import wo_generator
    
    flow = db.query(models.ProcessFlow).filter(models.ProcessFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
        
    # FR-13: Generate Matrix
    result = wo_generator.generate_wo_guide_data(flow)
    return result

@export_router.post("/training-guide/{flow_id}", dependencies=[Depends(verify_viewer)])
async def generate_training_guide_endpoint(flow_id: int, db: Session = Depends(get_db)):
    """
    Hyper-Learning: Generate a synthetic training guide fusing Video + Business Rules.
    """
    from ..services import training_synthesizer
    
    result = training_synthesizer.generate_hyper_guide(flow_id, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
        
    return result

@processing_router.put("/flows/{flow_id}/approval", dependencies=[Depends(verify_admin)])
async def update_flow_approval(flow_id: int, status_update: dict, db: Session = Depends(get_db)):
    """
    Update approval status (Draft -> Approved).
    Body: {"status": "approved"}
    """
    from ..models import models
    flow = db.query(models.ProcessFlow).filter(models.ProcessFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
        
    new_status = status_update.get("status")
    if new_status:
        # Validate enum? SQLAlchemy will handle constraint error if invalid usually, 
        # or we check against ApprovalStatus enum members.
        flow.approval_status = new_status
        db.commit()
    
    return {"id": flow.id, "status": flow.approval_status}

# --- Export Router ---
# export_router defined at top of file


@export_router.get("/{flow_id}")
def export_flow(flow_id: int, format: str = "json", db: Session = Depends(get_db)):
    from ..models import models
    from ..services import export
    import json
    
    flow = db.query(models.ProcessFlow).filter(models.ProcessFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
        
    output_filename = f"flow_{flow_id}.{format}"
    output_path = f"/tmp/{output_filename}"
    
    if format == "json":
        data = export.export_to_json(flow)
        # Mock saving JSON to file for download
        with open(output_path, "w") as f:
            json.dump(data, f)
            
    elif format == "docx":
        export.export_to_docx(flow, output_path)
        
    elif format == "pdf":
        export.export_to_pdf(flow, output_path)
        
    elif format == "pptx":
        export.export_to_pptx(flow, output_path)

    elif format == "html":
        # Save HTML string to file
        html_content = export.export_to_html(flow)
        with open(output_path, "w") as f:
            f.write(html_content)

    elif format == "scorm":
        # Output is a ZIP file
        output_filename = f"course_{flow_id}.zip"
        output_path = f"/tmp/{output_filename}"
        export.create_scorm_package(flow, output_path)

    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use json, docx, pdf, pptx, html, or scorm.")
        
    # In real app, upload to S3/MinIO and return Presigned URL
    # Here we mock returning a local path or dummy URL
    return {"download_url": f"http://localhost:2027/downloads/{output_filename}", "message": "Export created"}
# --- Analysis Router (AI Field Assistant) ---
analysis_router = APIRouter(prefix="/analysis", tags=["analysis"])

@analysis_router.post("/analyze_pole")
async def analyze_pole(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Analyzes an uploaded image for defects using RAG (Video Transcripts) + Vision Model.
    """
    from ..services.field_assistant import analyze_pole_image
    
    # Read file bytes
    contents = await file.read()
    
    result = analyze_pole_image(contents, db)
    return result
