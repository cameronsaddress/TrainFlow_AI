import requests
import sys

def recover_course():
    print("🚀 triggering Robust Course Generation (Utility Pole Training)...")
    url = "http://localhost:2027/api/curriculum/generate_structure"
    
    payload = {
        "topic": "Utility Pole Training",
        "audience": "Field Technicians",
        "modality": "VIDEO_COURSE"
    }
    
    try:
        # Use stream=True to see progress
        with requests.post(url, json=payload, stream=True) as r:
            if r.status_code != 200:
                print(f"❌ Error: {r.status_code} - {r.text}")
                return
                
            print("✅ Pipeline Started! Streaming logs:\n")
            for line in r.iter_lines():
                if line:
                    print(line.decode('utf-8'))
                    
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    recover_course()
