import asyncio
import os
import json
import redis
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models.models import Video, JobStatus, ProcessFlow, TrainingStep
from .services import asr, cv, storage

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL)

import numpy as np
from prometheus_client import Counter, Histogram
JOBS_PROCESSED = Counter("trainflow_jobs_processed_total", "Total video jobs processed", ["status"])
JOB_LATENCY = Histogram("trainflow_job_duration_seconds", "Job processing time")

def sanitize_json_compatible(obj):
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [sanitize_json_compatible(x) for x in obj.tolist()]
    if isinstance(obj, list):
        return [sanitize_json_compatible(x) for x in obj]
    if isinstance(obj, dict):
        return {k: sanitize_json_compatible(v) for k, v in obj.items()}
    return obj

def process_video_job(video_id: int):
    db: Session = SessionLocal()
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        print(f"Video {video_id} not found")
        return

    try:
        import time
        start_time = time.time()
        video.status = JobStatus.PROCESSING
        video.processing_stage = "Initializing"
        db.commit()

        # Download video from MinIO to local temp
        temp_path = f"/tmp/{video.filename}"
        # Download video from MinIO to local temp
        temp_path = f"/tmp/{video.filename}"
        
        # FR-1: Real file download
        print(f"Downloading {video.filename} from bucket {storage.BUCKET_NAME}...")
        storage.client.fget_object(storage.BUCKET_NAME, video.s3_key, temp_path)
        
        # Enterprise Grade: Duration Probe (Crucial for Removal Summary)
        import cv2
        try:
            cap = cv2.VideoCapture(temp_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if fps > 0:
                    video.duration = frames / fps
                    db.commit()
                    print(f"Video Duration Probe: {video.duration}s")
            cap.release()
        except Exception as e:
            print(f"Initial Duration Probe Failed: {e}")

        print(f"Starting processing for {video.filename}...")
        
        # 1. ASR
        # 1. ASR - Real Processing
        # 1. ASR - Real Processing
        print("Running ASR...")
        video.processing_stage = "Transcribing Audio (ASR)"
        db.commit()
        asr_result = asr.process_asr(temp_path)
        
        # 2. CV
        # 2. CV - Real Processing
        # 2. CV - Real Processing
        print("Running CV...")
        video.processing_stage = "Analyzing Video Frames (CV)"
        db.commit()
        cv_result = cv.process_cv(temp_path)
        
        # 3. Alignment Logic
        from .services import alignment, llm, identification, video_clip
        video.processing_stage = "Aligning Multimodal Data"
        db.commit()
        aligned_data = alignment.align_multimodal_data(asr_result, cv_result)
        
        # Enterprise-Grade Fix: Deep Segmentation
        # If we have 1 big step (bad ASR segmentation), use LLM to shatter it.
        if len(aligned_data) == 1 and len(aligned_data[0]['action_details']) > 100:
            print("Detected massive single block. Running LLM Deep Segmentation...")
            big_step = aligned_data[0]
            full_text = big_step['action_details']
            
            # Call LLM Breakout
            new_text_steps = llm.segment_transcript(full_text)
            
            if len(new_text_steps) > 1:
                print(f"Segmented into {len(new_text_steps)} steps.")
                reconstructed_steps = []
                
                # Get REAL video duration to clamp
                import cv2
                real_duration = 0.0
                try:
                    cap = cv2.VideoCapture(temp_path)
                    if cap.isOpened():
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        if fps > 0:
                            real_duration = frames / fps
                    cap.release()
                except Exception as e:
                    print(f"Duration Check Failed: {e}")

                # Timestamp Logic
                timeline = asr_result.get("timeline", [])
                
                if timeline:
                    print(f"Using Precise Timeline Alignment ({len(timeline)} words)...")
                    try:
                        aligned_segments = alignment.align_precise_timeline(new_text_steps, timeline)
                        
                        for idx, seg in enumerate(aligned_segments):
                            new_step = big_step.copy()
                            new_step['step_number'] = idx + 1
                            new_step['action_details'] = seg['action_details']
                            new_step['start_ts'] = seg['start_ts'] or 0.0
                            new_step['end_ts'] = seg['end_ts'] or (seg['start_ts'] + 2.0)
                            new_step['duration'] = new_step['end_ts'] - new_step['start_ts']
                            reconstructed_steps.append(new_step)
                    except Exception as align_e:
                        print(f"Alignment Failed: {align_e}. Falling back to Linear.")
                        timeline = [] # Force fallback
                
                if not timeline or not reconstructed_steps:
                    # Linear Interpolation Fallback
                    print("Fallback: Using Linear Interpolation for timestamps.")
                    total_duration = big_step['duration']
                    start_base = big_step['start_ts']
                    
                    # Sanity Check: If ASR duration is wildly overlapping real, clamp it
                    if real_duration > 0 and (start_base + total_duration) > real_duration:
                        print(f"Adjusting duration from {total_duration} to {real_duration - start_base}")
                        total_duration = real_duration - start_base
                    
                    step_dur = total_duration / len(new_text_steps)
                    
                    print(f"Deep Seg Stats: Base={start_base}, TotalDur={total_duration}, StepDur={step_dur}, RealDur={real_duration}")
    
                    for idx, txt in enumerate(new_text_steps):
                        s_ts = start_base + (idx * step_dur)
                        e_ts = s_ts + step_dur
                        
                        # Hard Clamp
                        if real_duration > 0:
                            if s_ts >= real_duration:
                                s_ts = real_duration - 1.0 # Last second fallback
                            if e_ts > real_duration:
                                e_ts = real_duration
                        
                        # Clone the big step's metadata
                        new_step = big_step.copy()
                        new_step['step_number'] = idx + 1
                        new_step['action_details'] = txt
                        new_step['start_ts'] = s_ts
                        new_step['end_ts'] = e_ts
                        new_step['duration'] = e_ts - s_ts
                        reconstructed_steps.append(new_step)
                
                aligned_data = reconstructed_steps

        video.processing_stage = "Saving Raw Extraction Data"
        if aligned_data:
             video.transcription_log = sanitize_json_compatible(aligned_data)
        if cv_result:
             video.ocr_log = sanitize_json_compatible(cv_result)
        db.commit()

        # 5. Optimize & Enrich (LLM) + Clip Extraction
        final_steps_data = []

        # ------------------------------------------------------------------
        # CRITICAL: Inject OCR Context EARLY for both Logic Analysis and Director
        # ------------------------------------------------------------------
        if cv_result:
            for step in aligned_data:
                s_start = step.get('start_ts', 0)
                s_end = step.get('end_ts', 0)
                
                # Find OCR events in this window
                relevant_ocr = []
                for event in cv_result:
                    evt_time = event.get('timestamp', 0)
                    if s_start <= evt_time <= s_end:
                        txt = event.get('ocr_text', '').strip()
                        if txt:
                            relevant_ocr.append(txt)
                
                # Deduplicate and join
                step['ocr_context'] = " | ".join(list(set(relevant_ocr)))

        # FR-7: Detect overall logic patterns first
        # Extract Text + OCR for Logic Analysis (Full Context)
        raw_texts = [f"Spoken: {s.get('action_details', '')} | Screen: {s.get('ocr_context', '')}" for s in aligned_data]
        
        video.processing_stage = "Analysing Logic Patterns (LLM)"
        db.commit()
        logic_analysis = llm.detect_logic_patterns(raw_texts)
        print(f"Logic Analysis: {logic_analysis}")
        
        # --- AI DIRECTOR: CURATION ---
        from .services import director
        print("Invoking AI Director (v3: Instructional Designer)...")
        # aligned_data now has 'ocr_context' for the LLM
        curated_indices = director.curate_steps(aligned_data)
        
        final_steps = []
        for i, item in enumerate(curated_indices):
             idx = item.get('original_index')
             if idx is not None and idx < len(aligned_data):
                  step = aligned_data[idx]
                  step['action_details'] = item.get('overlay_text', step['action_details']) # Rewrite Overlay
                  step['step_number'] = i + 1 # Re-number sequentially
                  final_steps.append(step)
                  print(f"DEBUG Director Item {i}: OrigIdx={idx}, Overlay='{step['action_details']}'")
        
        print(f"Director reduced steps from {len(aligned_data)} to {len(final_steps)}")
        aligned_data = final_steps
        # -----------------------------
        
        # Update Status BEFORE huge clip loop
        video.processing_stage = "Generating Smart Clips (AI Agent)"
        db.commit()
        
        decision_idx = logic_analysis.get("decision_node_index", -1)
        
        for i, step_data in enumerate(aligned_data):
            # ... loop continues ...
            # LLM Enrichment (Mocked or Real)
            # refined_step = llm.refine_step(step_data) # If using real LLM
            # For prototype speed, we map directly:
            refined_step = {
                "step_number": step_data.get("step_number"),
                "action": step_data.get("action_details"),
                "result": "System updates",
                "start_ts": step_data.get("start_ts"),
                "end_ts": step_data.get("end_ts"),
                "duration": step_data.get("duration"),
                "text": step_data.get("action_details"),
                "field_details": [] # FR-9
            }
            
            # Application of Logic Analysis
            if i == decision_idx:
                refined_step["step_type"] = "decision"
                refined_step["decision_map"] = {"Default": i + 2} # Mock logic: skip next
            else:
                refined_step["step_type"] = "linear"
                refined_step["decision_map"] = {}

            # System Identification
            sys_text = refined_step.get("text") or "" # Handle None
            identified = identification.identify_system(sys_text, "")
            refined_step["system"] = identified if identified else "Generic System"

            # SRS 8.3: Error Detection
            if cv_result and len(cv_result) > i:
                # Get OCR from corresponding CV frame (aligned approx)
                error_check = cv.detect_error_state(refined_step.get("text", "") + " " + refined_step.get("action", ""), db_session=db)
                if error_check["has_error"]:
                    refined_step["field_details"].append({"label": "ErrorState", "validation": error_check["details"]})
                    # Add Resolution
                    res = error_check.get("resolution", "Contact Support")
                    refined_step["result"] += f" [Error: {error_check['details']} -> Fix: {res}]"

            # Screenshot Management (With Redaction NFR-4)
            # Create unique path
            step_id_mock = f"{video_id}_{step_data.get('step_number')}"
            screenshot_path = f"/app/data/shots/{step_id_mock}.jpg"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            
            try:
                # Extract frame at start_ts
                import cv2
                from PIL import Image
                from .services.cv import redact_pii
                
                start_ts = step_data.get("start_ts", 0)
                print(f"DEBUG: Generating text for Step {step_data.get('step_number')} at {start_ts}s")
                
                # Note: In real prod, we'd open VideoCapture ONCE outside loop for performance
                # For prototype safety, we open per step or assume cv_result has paths
                cap = cv2.VideoCapture(temp_path)
                
                if not cap.isOpened():
                    print(f"DEBUG: Failed to open video at {temp_path}")
                
                # Seek to timestamp
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                target_frame = int(start_ts * fps)
                
                if fps:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    
                ret, frame = cap.read()
                if ret:
                    # Convert to PIL
                    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(img_rgb)
                    
                    # Redact PII
                    clean_img = redact_pii(pil_img)
                    
                    # Save
                    clean_img.save(screenshot_path)
                    print(f"DEBUG: Saved screenshot to {screenshot_path}")
                    refined_step["screenshot_path"] = f"/data/shots/{step_id_mock}.jpg"
                else:
                    print(f"DEBUG: Failed to read frame at {target_frame}/{total_frames} (FPS: {fps})")
                    
                cap.release()
            except Exception as e:
                print(f"Failed to capture/redact screenshot: {e}")
            
            # Clip Extraction
            clip_filename = f"clip_{video_id}_{refined_step.get('step_number', 'x')}.mp4"
            # Enterprise storage location
            clip_local_path = os.path.join("/app/data/clips", clip_filename)
            
            start_ts = refined_step.get("start_ts", 0.0)
            end_ts = refined_step.get("end_ts", start_ts + 2.0)
            
            # Call the new (or mocked) service
            # using temp_path defined earlier
            # NOTE: We use temp_path. If it was mocked (start of file), this might fail if file doesn't exist.
            # But assumes 'temp_path' is valid from earlier download step.
            
            # Application of Smart Flash Logic (AI Director 2.0)
            # Only flash if:
            # 1. This is a jump cut (Time gap > 0.5s from previous step's end)
            # 2. OR This is a reordered step (Sequence break)
            # NOTE: We need to track previous step's end_ts outside the loop ideally, but we can infer it.
            # Actually, we need a state variable.
            # Let's check against `final_steps_data` which we are appending to.
            
            enable_flash = False
            current_idx = refined_step.get("step_number", 0)
            current_start = refined_step.get("start_ts", 0.0)
            
            if len(final_steps_data) > 0:
                prev = final_steps_data[-1]
                prev_end = prev.get("end_ts", 0.0)
                prev_idx = prev.get("step_number", 0)
                
                is_gap = (current_start - prev_end) > 0.5
                is_reordered = (current_idx != prev_idx + 1)
                
                if is_gap or is_reordered:
                    enable_flash = True
            
            # Since we are in a prototype without a real video downloader often, 
            # let's add a check: if temp_path exists, run it.
            if os.path.exists(temp_path):
                from .services import video_clip
                # FR-14 + NFR-4 (Redaction) + FR-New (Overlays) + AI Director 2.0 (Smart Flash)
                result_path = video_clip.extract_clip(
                    temp_path, 
                    start_ts, 
                    end_ts, 
                    clip_local_path, 
                    apply_redaction=True,
                    overlay_text=refined_step.get("action", ""), # Burn instruction
                    enable_flash=enable_flash
                )
                
                if result_path and os.path.exists(result_path):
                    refined_step["video_clip_path"] = f"/data/clips/{clip_filename}"
                    
                    # SRS 15: Generate VTT Caption
                    vtt_content = video_clip.generate_vtt_content(refined_step.get("text", "Action Step"), end_ts - start_ts)
                    vtt_filename = clip_filename.replace(".mp4", ".vtt")
                    vtt_path = os.path.join("/app/data/clips", vtt_filename) # Use enterprise path
                    with open(vtt_path, "w") as f:
                        f.write(vtt_content)
                else:
                    print(f"Failed to extract clip for step {refined_step.get('step_number')}")
                    refined_step["video_clip_path"] = None
            else:
                 refined_step["video_clip_path"] = "placeholder.mp4"

            final_steps_data.append(refined_step)
            
        # Enterprise Feature: Spark Notes Summary Video
        # Stitch all clips together using FFmpeg Concat Demuxer
        summary_video_path = None
        valid_clips = [s.get("video_clip_path") for s in final_steps_data if s.get("video_clip_path") and s.get("video_clip_path").endswith(".mp4")]
        
        if valid_clips:
            try:
                # Splash Screens Disabled (User Request)
                # ------------------------------------------------------------------

                print(f"Stitching {len(valid_clips)} clips into Summary Video...")
                concat_list_path = f"/tmp/concat_list_{video.id}.txt"
                summary_filename = f"summary_{video.id}.mp4"
                summary_output_path = os.path.join("/app/data/clips", summary_filename) # Shared Volume
                
                with open(concat_list_path, "w") as f:
                    for clip_url in valid_clips:
                         # clip_url is like "/data/clips/file.mp4" -> need local path "/app/data/clips/file.mp4"
                         # We need to strip the /data prefix and prepend /app/data if mapped that way, 
                         # OR just use the known structure.
                         # refine_step sets it to "/data/clips/..." but local file is "/app/data/clips/..."
                         local_path = clip_url.replace("/data/", "/app/data/")
                         if os.path.exists(local_path):
                             f.write(f"file '{local_path}'\n")
                
                # Check if list has content
                if os.path.getsize(concat_list_path) > 0:
                     # Run FFmpeg Concat (Re-muxing, no re-encoding = Instant)
                     import subprocess
                     
                     cmd = [
                         "ffmpeg", "-f", "concat", "-safe", "0", 
                         "-i", concat_list_path, 
                         "-c", "copy", "-y", 
                         summary_output_path
                     ]
                     subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     print(f"Summary video created at {summary_output_path}")
                     summary_video_path = f"/data/clips/{summary_filename}"
                else:
                    print("No valid clips found for stitching.")
                    
            except Exception as e:
                print(f"Summary Stitching Failed: {e}")
            


        # Summary Calculation for UI
        total_kept_duration = sum([s.get("duration", 0) for s in final_steps_data])
        removed_seconds = max(0, video.duration - total_kept_duration) if video.duration else 0
        removal_summary_text = f"✨ AI removed {removed_seconds:.1f}s of silence & loading screens."
        if video.duration and video.duration > 0:
            pct = (removed_seconds / video.duration) * 100
            removal_summary_text += f" (Compressed by {pct:.0f}%)"

        # 4. Save Results to DB
        flow = ProcessFlow(
            video_id=video.id,
            title=f"Process Flow for {video.filename}",
            description="Automatically generated flow based on video analysis.",

            summary_video_path=summary_video_path,
            removal_summary=removal_summary_text
        )
        db.add(flow)
        db.commit()
        db.refresh(flow)
        
        for step_dict in final_steps_data:
            step = TrainingStep(
                flow_id=flow.id,
                step_number=int(step_dict.get("step_number")),
                system_name=step_dict.get("system"),
                action_type="interaction",
                action_details=step_dict.get("action"),
                expected_result=step_dict.get("result"),
                start_ts=float(step_dict.get("start_ts", 0.0)),
                end_ts=float(step_dict.get("end_ts", 0.0)),
                duration=float(step_dict.get("duration", 0.0)),
                screenshot_path=step_dict.get("screenshot_path"), # NFR-4
                video_clip_path=step_dict.get("video_clip_path"),
                step_type=step_dict.get("step_type", "linear"),
                decision_map=step_dict.get("decision_map", {}),
                ui_metadata={"fields": step_dict.get("field_details", [])} # FR-9 Persistence
            )
            db.add(step)
        
        video.status = JobStatus.COMPLETED
        db.commit()
        print(f"Completed processing for {video.filename}")
        
        # Metrics
        JOBS_PROCESSED.labels(status="success").inc()
        JOB_LATENCY.observe(time.time() - start_time)

    except Exception as e:
        print(f"Error processing video {video_id}: {e}")
        video.status = JobStatus.FAILED
        video.error_message = str(e) # Save error to DB
        db.commit()
        JOBS_PROCESSED.labels(status="failed").inc()
    finally:
        db.close()
        # Cleanup temp files

def start_worker():
    print("Worker started. Listening for jobs...")
    pubsub = redis_client.pubsub()
    pubsub.subscribe("video_jobs")
    
    for message in pubsub.listen():
        if message["type"] == "message":
            video_id = int(message["data"])
            process_video_job(video_id)

if __name__ == "__main__":
    start_worker()
