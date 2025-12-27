import os
import logging
from sqlalchemy.orm import Session
from ..models import knowledge as k_models
from ..db import SessionLocal
from . import asr, cv
import cv2

# Setup
import subprocess
import json
logger = logging.getLogger(__name__)

def ingest_video(video_id: int):
    """
    Background Task: Encapsulates Video -> Audio/Frames -> Text (ASR + OCR) -> DB
    Strictly Indexing. No Logic.
    """
    print(f"Background Task Started: Ingesting Video ID {video_id}", flush=True)
    db = SessionLocal()
    try:
        video = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.id == video_id).first()
        if not video:
            print(f"Video ID {video_id} not found", flush=True)
            return

        # Idempotency Check: Prevent double-processing
        if video.status != k_models.DocStatus.PENDING:
            print(f"Video ID {video_id} is in state {video.status}. Skipping ingestion.", flush=True)
            return
            
        video.status = k_models.DocStatus.INDEXING
        db.commit()

        if not os.path.exists(video.file_path):
             raise FileNotFoundError(f"File {video.file_path} not found")
        
        # Helper logging
        import psutil
        def log_mem(stage):
             m = psutil.virtual_memory()
             print(f"[DEBUG] {stage} | Free: {m.available/1e9:.2f}GB | Used: {m.percent}%", flush=True)

        # 1. ASR (Audio -> Text) via Subprocess
        log_mem("PRE-ASR")
        print(f"Starting ASR (Subprocess) for {video.filename}...", flush=True)
        asr_output_path = f"{video.file_path}.asr.json"
        
        try:
            cmd = ["python3", "-m", "app.services_cli", "asr", video.file_path, asr_output_path]
            # Capture output to log explicit subprocess errors
            subprocess.run(cmd, check=True, cwd=os.getcwd())
            log_mem("POST-ASR")
            
            with open(asr_output_path, 'r') as f:
                asr_result = json.load(f)
                
            full_transcript = asr_result.get("text", "")
            print(f"ASR Subprocess Complete. Length: {len(full_transcript)} chars.", flush=True)
            
            # Cleanup output file
            if os.path.exists(asr_output_path):
                os.remove(asr_output_path)
                
        except  subprocess.CalledProcessError as e:
            print(f"ASR Subprocess Failed with code {e.returncode}", flush=True)
            raise e
        except Exception as e:
            print(f"ASR Result Parsing Failed: {e}", flush=True)
            raise e
        
        # 2. OCR (Frames -> Text) via Subprocess
        log_mem("PRE-OCR")
        print(f"Starting OCR (Subprocess) for {video.filename}...", flush=True)
        ocr_output_path = f"{video.file_path}.ocr.json"
        
        try:
            cmd = ["python3", "-m", "app.services_cli", "ocr_sampling", video.file_path, ocr_output_path]
            subprocess.run(cmd, check=True, cwd=os.getcwd())
            
            with open(ocr_output_path, 'r') as f:
                ocr_result_data = json.load(f)
                
            full_ocr = ocr_result_data.get("full_text", "")
            ocr_json_data = ocr_result_data.get("json_data", [])
            video.duration_seconds = ocr_result_data.get("duration", 0.0)
            
            print(f"OCR Subprocess Complete. Sampled {len(ocr_json_data)} frames.", flush=True)
            
            # Cleanup output file
            if os.path.exists(ocr_output_path):
                os.remove(ocr_output_path)
                
        except subprocess.CalledProcessError as e:
            print(f"OCR Subprocess Failed with code {e.returncode}", flush=True)
            raise e
        except Exception as e:
             print(f"OCR Result Parsing Failed: {e}", flush=True)
             raise e
        
        # 3. Save to DB
        video.transcript_text = full_transcript
        video.transcript_json = {
            "timeline": asr_result.get("timeline", []),
            "speaker_segments": asr_result.get("speaker_segments", []),
            "segments": asr_result.get("segments", [])
        }
        
        video.ocr_text = full_ocr
        video.ocr_json = ocr_json_data
        
        # Metadata Calculation
        word_count = len(full_transcript.split()) if full_transcript else 0
        current_meta = video.metadata_json or {}
        current_meta["word_count"] = word_count
        video.metadata_json = current_meta

        video.status = k_models.DocStatus.READY
        db.commit()
        print(f"Ingestion Complete for Video {video_id}", flush=True)

    except Exception as e:
        print(f"Video Ingestion Failed: {e}", flush=True)
        video.status = k_models.DocStatus.FAILED
        # video.error_message = str(e) # Add error msg col if needed later
        db.commit()
    finally:
        db.close()
