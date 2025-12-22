import requests
import sys

API_URL = "http://localhost:8000/api"

def verify_latest():
    print("Fetching Latest Job...")
    try:
        r = requests.get(f"{API_URL}/process/jobs")
        if r.status_code != 200:
            print(f"FAIL: /process/jobs returned {r.status_code}")
            return
            
        jobs = r.json()
        if not jobs:
            print("No jobs found.")
            return
            
        # Sort desc
        jobs.sort(key=lambda x: x["id"], reverse=True)
        latest_job = jobs[0]
        
        print(f"Latest Job ID: {latest_job['id']}, Status: {latest_job['status']}")
        
        if latest_job['status'] != "COMPLETED":
            print("Job not completed yet.")
            return

        video_id = latest_job['video_id']
        
        # 1. Check Flow
        r_flow = requests.get(f"{API_URL}/process/flows/by-video/{video_id}")
        if r_flow.status_code == 200:
            flow = r_flow.json()
            print(f"SUCCESS: Flow {flow['id']} exists.")
            
            # 2. Check WO Guide
            r_wo = requests.post(f"{API_URL}/process/flows/{flow['id']}/generate-wo")
            if r_wo.status_code == 200:
                print("SUCCESS: WO Guide Generated.")
                print(str(r_wo.json())[:200])
            else:
                print(f"FAIL: WO Guide Error: {r_wo.text}")
        else:
            print(f"FAIL: Flow not found for video {video_id}")
            
        # 3. Check Transcription/Diarization
        r_trans = requests.get(f"{API_URL}/uploads/{video_id}/transcription")
        if r_trans.status_code == 200:
            data = r_trans.json()
            log = data.get("transcription_log", [])
            speakers = set(s.get("speaker", "Unknown") for s in log)
            print(f"Speakers Found: {list(speakers)}")
            if len(log) > 0 and "speaker" in log[0]:
                 print("SUCCESS: Speaker field exists in steps.")
            else:
                 print("FAIL/WARN: Speaker field missing or log empty.")
        else:
            print("FAIL: Transcription fetch error.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_latest()
