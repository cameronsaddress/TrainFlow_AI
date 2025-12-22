import requests
import json
import time
import sys

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

API_URL = "http://localhost:8000/api"

def run_test():
    print("--- Starting Hyper-Learning Verification ---")
    
    # 1. Get Latest Video (assuming one exists from previous tests)
    print("[*] Fetching latest video...")
    headers = {"Authorization": "Bearer dev-admin-token"}
    try:
        resp = requests.get(f"{API_URL}/uploads/", headers=headers)
        if resp.status_code != 200:
            print(f"{RED}[-] Auth Error: {resp.status_code} {resp.text}{RESET}")
            return
            
        videos = resp.json()
        if not videos:
            print(f"{RED}[-] No videos found. Please run e2e pipeline first.{RESET}")
            return
            
        # Find video with steps
        video = None
        for v in videos:
            if v.get('steps_count', 0) > 0:
                video = v
                break
        
        if not video:
            print(f"{RED}[-] No videos with active steps found. Processing might be incomplete.{RESET}")
            # Fallback to first
            video = videos[0]
            
        video_id = video['id']
        # Extract flow_id if available
        target_flow_id = video.get('flow_id')
        print(f"{GREEN}[+] Selected Video ID: {video_id}, Steps: {video.get('steps_count')}, Flow: {target_flow_id}{RESET}")
    except Exception as e:
         print(f"{RED}[-] API Error: {repr(e)}{RESET}")
         import traceback
         traceback.print_exc()
         return

    # 2. Extract Business Rules
    print("[*] Verifying available Rules...")
    try:
        rules = requests.get(f"{API_URL}/knowledge/rules", headers=headers).json()
    except:
        rules = []
        
    print(f"    Found {len(rules)} active rules.")
    # ... (omitted)

    # 3. Get Process Flow ID
    if not target_flow_id:
        print("[*] Flow ID not found in video object, probing...")
        for fid in range(1, 100): # Increased range and check 64 specially?
             if fid == 64: pass 
             try:
                r = requests.post(f"{API_URL}/process/flows/{fid}/generate-wo", headers=headers) 
                if r.status_code == 200:
                    target_flow_id = fid
                    print(f"{GREEN}[+] Found valid Flow ID: {fid}{RESET}")
                    break
             except:
                pass
            
    if not target_flow_id:
        # Fallback for demo: Try to force ID 1 or 64 if they exist
        target_flow_id = video_id # Often 1:1 in seeding
        print(f"[*] Trying Video ID as Flow ID: {target_flow_id}")
            
    if not target_flow_id:
        print(f"{RED}[-] No process flow found. Skipping generation.{RESET}")
        return

    # 4. Generate Hyper-Guide
    print(f"[*] Generating Hyper-Guide for Flow {target_flow_id}...")
    start_time = time.time()
    resp = requests.post(f"{API_URL}/export/training-guide/{target_flow_id}", headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"{GREEN}[+] Guide Generated in {time.time() - start_time:.2f}s{RESET}")
        print(json.dumps(data, indent=2))
        
        # Validation
        if len(data.get("modules", [])) > 0:
            print(f"{GREEN}[+] Success: {len(data['modules'])} synthesized modules created.{RESET}")
            # Check for warnings
            warn_count = sum(1 for m in data['modules'] if m.get("warnings"))
            print(f"    - Steps with Compliance Warnings: {warn_count}")
        else:
            print(f"{RED}[-] Warning: Guide empty.{RESET}")
    else:
        print(f"{RED}[-] Generation Failed: {resp.text}{RESET}")

if __name__ == "__main__":
    run_test()
