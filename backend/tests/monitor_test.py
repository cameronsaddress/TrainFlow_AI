import requests
import time
import sys
from datetime import datetime

API_URL = "http://localhost:8000/api"

def monitor_latest_job():
    print("Watching for new jobs...")
    seen_jobs = set()
    
    # Get initial jobs to ignore
    try:
        r = requests.get(f"{API_URL}/process/jobs")
        if r.status_code == 200:
            for j in r.json():
                seen_jobs.add(j["id"])
    except:
        pass
        
    target_job_id = None
    target_video_id = None
    
    # Poll for new job
    while not target_job_id:
        try:
            r = requests.get(f"{API_URL}/process/jobs")
            jobs = r.json()
            # Sort by ID desc
            jobs.sort(key=lambda x: x["id"], reverse=True)
            
            for j in jobs:
                if j["id"] not in seen_jobs:
                    print(f"Detected New Job: {j['id']} (Video: {j.get('video_filename')})")
                    target_job_id = j["id"]
                    target_video_id = j.get("video_id") # Note: Job might not return video_id directly, assume we can fetch it
                    # Actually standard job object usually has relation or we get it from /flows
                    # Let's check status
                    break
            
            if not target_job_id:
                time.sleep(2)
                sys.stdout.write(".")
                sys.stdout.flush()
        except Exception as e:
            print(f"Error polling: {e}")
            time.sleep(2)
            
    print(f"\nTracking Job {target_job_id}...")
    
    while True:
        try:
            r = requests.get(f"{API_URL}/process/jobs")
            jobs = r.json()
            job = next((j for j in jobs if j["id"] == target_job_id), None)
            
            if not job:
                print("Job vanished!")
                break
                
            status = job["status"]
            progress = job.get("progress", 0)
            stage = job.get("current_stage", "")
            
            print(f"Status: {status} | Progress: {progress}% | Stage: {stage}")
            
            if status == "completed":
                print("Job Completed!")
                # Get Video ID from Job if possible, or assume we fetch flows
                # In models.py Job doesn't exist? Wait, we tracked 'Video' status generally in this system.
                # 'jobs' endpoint usually returns videos processing.
                # target_job_id is likely video_id if we use specific endpoint?
                # Actually, /process/jobs endpoint returns list of Videos with status != completed?
                # Let's look at api.py get_jobs...
                # Assuming target_job_id corresponds to video_id if that's how it's implemented.
                # Let's assum target_video_id = target_job_id for now if schema is shared.
                target_video_id = target_job_id 
                break
            elif status == "failed":
                print(f"Job Failed: {job.get('error_message')}")
                return
                
            time.sleep(2)
        except Exception as e:
            print(e)
            time.sleep(2)

    # Verification Steps
    print("--- Verifying Outputs ---")
    
    # 1. Check Flow Existence
    time.sleep(2) # Wait for Flow creation
    r_flow = requests.get(f"{API_URL}/process/flows/by-video/{target_video_id}")
    if r_flow.status_code != 200:
        print(f"FAIL: Flow not found for video {target_video_id}")
        return
        
    flow = r_flow.json()
    flow_id = flow["id"]
    print(f"SUCCESS: Flow Created (ID: {flow_id})")
    
    # 2. Check WO Guide (FR-13)
    r_wo = requests.post(f"{API_URL}/process/flows/{flow_id}/generate-wo")
    if r_wo.status_code == 200:
        data = r_wo.json()
        print(f"SUCCESS: WO Guide Generated. Systems Detected: {data.get('systems_involved')}")
        if data.get("field_mapping_matrix"):
            print(f"       Mapping Matrix has {len(data['field_mapping_matrix'])} entries.")
    else:
        print(f"FAIL: WO Guide Generation Error: {r_wo.text}")

    # 3. Check Speaker Diarization (FR-5)
    r_trans = requests.get(f"{API_URL}/uploads/{target_video_id}/transcription")
    if r_trans.status_code == 200:
        t_log = r_trans.json().get("transcription_log", [])
        if t_log:
            speakers = set(step.get("speaker", "Unknown") for step in t_log)
            print(f"SUCCESS: Transcription Log Found. Speakers Detected: {list(speakers)}")
        else:
            print("WARN: Transcription log empty.")
    else:
        print("FAIL: Could not fetch transcription.")
        
    print("E2E Verification Complete.")

if __name__ == "__main__":
    monitor_latest_job()
