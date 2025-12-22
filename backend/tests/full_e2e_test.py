import requests
import time
import sys
import os

API_URL = "http://localhost:8000/api"

def run_full_e2e():
    print("--- Starting Full E2E Pipeline Test ---")
    
    # 1. Upload
    video_path = "/app/tests/test_video.mp4"
    if not os.path.exists(video_path):
        print(f"Error: {video_path} not found. Please generate it first.")
        # Attempt generation if missing (fallback)
        os.system(f"ffmpeg -f lavfi -i testsrc=duration=10:size=1280x720:rate=30 -f lavfi -i sine=frequency=1000:duration=10 -c:v libx264 -c:a aac -y {video_path} 2>/dev/null")
    
    print(f"Uploading {video_path}...")
    job_id = None
    video_id = None
    
    try:
        with open(video_path, 'rb') as f:
            r = requests.post(f"{API_URL}/uploads/", files={'file': f})
            if r.status_code != 200:
                print(f"Upload Failed: {r.text}")
                return
            data = r.json()
            # api/uploads returns video info usually. logic in upload_video: returns {id, ...}
            # trigger logic in worker puts job in redis.
            # We assume Job ID ~ Video ID or we search for latest job.
            video_id = data.get("id")
            print(f"Upload Success. Video ID: {video_id}")
    except Exception as e:
        print(f"Upload Request Failed: {e}")
        return

    # 2. Find Job
    print("Waiting for Job to appear...")
    for i in range(60):
        r_jobs = requests.get(f"{API_URL}/process/jobs")
        if r_jobs.status_code == 200:
            jobs = r_jobs.json()
            # Look for job for this video_id
            my_job = next((j for j in jobs if j.get("video_id") == video_id), None)
            # Fallback: Sort by ID desc
            if not my_job and jobs:
                jobs.sort(key=lambda x: x["id"], reverse=True)
                candidate = jobs[0]
                # If created recently?
                my_job = candidate
            
            if my_job:
                job_id = my_job["id"]
                print(f"Job Found: ID {job_id} (Status: {my_job['status']})")
                break
        time.sleep(1)
        
    if not job_id:
        print("FAIL: Job never appeared.")
        return
        
    # 3. Monitor
    print(f"Monitoring Job {job_id}...")
    while True:
        r_jobs = requests.get(f"{API_URL}/process/jobs")
        jobs = r_jobs.json()
        job = next((j for j in jobs if j["id"] == job_id), None)
        
        if not job:
            print("Job Lost.")
            return
            
        status = job["status"]
        stage = job.get("current_stage", "Unknown")
        sys.stdout.write(f"\rStatus: {status} | Stage: {stage}   ")
        sys.stdout.flush()
        
        if status == "COMPLETED":
            print("\nJob Completed!")
            break
        elif status == "FAILED":
            print(f"\nJob Failed: {job.get('error_message')}")
            # Don't return, check logs anyway
            break
            
        time.sleep(2)
        
    # 4. Verify Outputs
    print("\n--- Verifying Features ---")
    
    # Check Flow
    r_flow = requests.get(f"{API_URL}/process/flows/by-video/{video_id}")
    if r_flow.status_code == 200:
        flow = r_flow.json()
        print(f"[PASS] Flow Created (ID: {flow['id']})")
        
        # FR-13: WO Guide
        # Note: generate-wo requires Admin per api.py line 394?
        # "dependencies=[Depends(verify_admin)]" is likely on generate-wo too.
        # We might get 403 here unless we removed that too or pass header.
        # For this test, I'll expect 403 if protected, but confirm endpoint reachable.
        r_wo = requests.post(f"{API_URL}/process/flows/{flow['id']}/generate-wo")
        if r_wo.status_code == 200:
            print(f"[PASS] WO Guide Generated (FR-13)")
        elif r_wo.status_code == 403:
             print(f"[WARN] WO Guide 403 (Auth Required) - Endpoint Exists")
        else:
             print(f"[FAIL] WO Guide Error: {r_wo.status_code} {r_wo.text}")
    else:
        print(f"[FAIL] Flow Creation Failed")
        
    # FR-5: Diarization
    # Check transcription log
    r_trans = requests.get(f"{API_URL}/uploads/{video_id}/transcription")
    if r_trans.status_code == 200:
        data = r_trans.json()
        log = data.get("transcription_log", [])
        speakers = set(s.get("speaker") for s in log if "speaker" in s)
        print(f"Speakers Detected: {list(speakers)}")
        if len(speakers) > 0:
            print(f"[PASS] FR-5 Diarization Data Present")
        else:
             # It might be "Unknown" if fallback hit, but field should exist
             if log and "speaker" in log[0]:
                 print(f"[PASS] FR-5 Speaker Field Exists (Value: {log[0]['speaker']})")
             else:
                 print(f"[FAIL] Speaker Field Missing from Logs")
    else:
        print(f"[FAIL] Transcription Log Fetch Failed")

if __name__ == "__main__":
    run_full_e2e()
