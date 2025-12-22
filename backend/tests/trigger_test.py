import requests
import time
import sys
import os

API_URL = "http://localhost:8000/api"

def run_e2e_test():
    video_path = "/app/tests/test_video.mp4"
    if not os.path.exists(video_path):
        print(f"Error: {video_path} not found.")
        return

    print(f"Uploading {video_path}...")
    with open(video_path, 'rb') as f:
        files = {'file': f}
        try:
            r = requests.post(f"{API_URL}/uploads/", files=files)
            if r.status_code != 200:
                print(f"Upload Failed: {r.text}")
                return
            
            data = r.json()
            job_id = data.get("job_id")
            video_id = data.get("id")
            print(f"Upload Success. Job ID: {job_id}, Video ID: {video_id}")
            
            # Monitor
            print("Monitoring Job...")
            while True:
                r_status = requests.get(f"{API_URL}/process/jobs")
                jobs = r_status.json()
                
                # Find our job
                my_job = next((j for j in jobs if j["id"] == job_id), None)
                if not my_job:
                    print("Job lost?")
                    break
                
                status = my_job["status"]
                print(f"Status: {status} | Progress: {my_job.get('progress')}%")
                
                if status == "completed":
                    print("Job Completed!")
                    break
                elif status == "failed":
                    print(f"Job Failed: {my_job.get('error')}")
                    break
                    
                time.sleep(2)
                
            # Verify Flow
            if status == "completed":
                 r_flow = requests.get(f"{API_URL}/process/flows/by-video/{video_id}")
                 if r_flow.status_code == 200:
                     print("Flow Created Successfully.")
                     flow = r_flow.json()
                     print(f"Flow ID: {flow.get('id')}")
                     
                     # Test FR-13: WO Guide
                     print("Testing FR-13 (WO Guide Generation)...")
                     r_wo = requests.post(f"{API_URL}/process/flows/{flow.get('id')}/generate-wo")
                     if r_wo.status_code == 200:
                         print("WO Guide Generated OK.")
                         print(str(r_wo.json())[:100] + "...")
                     else:
                         print(f"WO Guide Failed: {r_wo.text}")
                 else:
                     print(f"Flow not found: {r_flow.text}")

        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    run_e2e_test()
