
import os
import json
import logging
import subprocess
from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import corpus_ingestor # Import to reuse logic if possible, or replicate

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RecoverJobs")

TARGET_FILES = [
    "Work Order Training - Day 2.mp4",
    "Work Order Training - Day 1 Part1.mp4"
]

def recover_video(video: k_models.VideoCorpus, db):
    logger.info(f"--- Recovering {video.filename} (ID: {video.id}) ---")
    
    # Reset status to allow processing if it thinks it's done or failed
    # Actually, let's just proceed with checks.
    
    asr_output_path = f"{video.file_path}.asr.json"
    ocr_output_path = f"{video.file_path}.ocr.json"
    
    # 1. ASR Recovery
    if os.path.exists(asr_output_path):
        logger.info(f"Found existing ASR output: {asr_output_path}")
    else:
        logger.info(f"ASR output missing. Re-running ASR for {video.filename}...")
        try:
            cmd = ["python3", "-m", "app.services_cli", "asr", video.file_path, asr_output_path]
            subprocess.run(cmd, check=True, cwd=os.getcwd())
            logger.info("ASR Subprocess Complete.")
        except Exception as e:
            logger.error(f"ASR Recovery Failed: {e}")
            return

    # 2. OCR Recovery
    if os.path.exists(ocr_output_path):
        logger.info(f"Found existing OCR output: {ocr_output_path}")
    else:
        logger.info(f"OCR output missing. Re-running OCR for {video.filename}...")
        try:
            cmd = ["python3", "-m", "app.services_cli", "ocr_sampling", video.file_path, ocr_output_path]
            subprocess.run(cmd, check=True, cwd=os.getcwd())
            logger.info("OCR Subprocess Complete.")
        except Exception as e:
            logger.error(f"OCR Recovery Failed: {e}")
            return

    # 3. Finalize Ingestion (Load & Save to DB)
    try:
        logger.info("Finalizing ingestion...")
        
        # Load ASR
        with open(asr_output_path, 'r') as f:
            asr_result = json.load(f)
        full_transcript = asr_result.get("text", "")
        
        # Load OCR
        with open(ocr_output_path, 'r') as f:
            ocr_result_data = json.load(f)
        full_ocr = ocr_result_data.get("full_text", "")
        ocr_json_data = ocr_result_data.get("json_data", [])
        
        # Update DB
        video.transcript_text = full_transcript
        video.transcript_json = {
            "timeline": asr_result.get("timeline", []),
            "speaker_segments": asr_result.get("speaker_segments", []),
            "segments": asr_result.get("segments", [])
        }
        
        video.ocr_text = full_ocr
        video.ocr_json = ocr_json_data
        video.duration_seconds = ocr_result_data.get("duration", 0.0)
        
        video.status = k_models.DocStatus.READY
        db.commit()
        logger.info(f"SUCCESS: {video.filename} is now READY.")
        
        # Optional: Cleanup? User might want to inspect, let's leave them for now or assume ingester cleanup logic
        # corpus_ingestor deletes them. Let's delete them to be clean.
        if os.path.exists(asr_output_path): os.remove(asr_output_path)
        if os.path.exists(ocr_output_path): os.remove(ocr_output_path)
        logger.info("Cleaned up intermediate files.")

    except Exception as e:
        logger.error(f"Finalization Failed: {e}")

def main():
    db = SessionLocal()
    try:
        videos = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename.in_(TARGET_FILES)).all()
        
        if not videos:
            logger.warning("No target videos found in DB!")
            # Fallback: Searching by partial match if exact match fails?
            all_videos = db.query(k_models.VideoCorpus).all()
            logger.info(f"Available videos: {[v.filename for v in all_videos]}")
            return

        for video in videos:
            recover_video(video, db)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
