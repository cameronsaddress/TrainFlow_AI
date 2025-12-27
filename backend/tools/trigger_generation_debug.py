
import requests
import json
import time

URL = "http://localhost:8000/api/curriculum/generate_structure"

def trigger():
    print(f"Triggering Generation at {URL}...")
    try:
        with requests.post(URL, stream=True) as r:
            r.raise_for_status()
            print("Response Status: 200 OK")
            print("Listening to stream...")
            
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    try:
                        data = json.loads(decoded)
                        msg_type = data.get("type")
                        if msg_type == "status":
                            print(f"[STATUS] {data.get('msg')}")
                        elif msg_type == "result":
                            print(f"[RESULT] payload keys: {data.get('payload', {}).keys()}")
                        elif msg_type == "error":
                            print(f"[ERROR] {data.get('msg')}")
                    except:
                        print(f"[RAW] {decoded}")
                        
        print("Stream Closed.")
            
    except Exception as e:
        print(f"Request Failed: {e}")

if __name__ == "__main__":
    trigger()
