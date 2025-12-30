
import requests
import json
import sys

API_URL = "http://localhost:2027/api"

DOC_ID = 10 # Known document
ANCHOR = "1.3 TRANSMISSION VOLTAGES"

def test_locate():
    print(f"Testing POST /documents/{DOC_ID}/locate with anchor '{ANCHOR}'...")
    try:
        res = requests.post(
            f"{API_URL}/knowledge/documents/{DOC_ID}/locate",
            json={"anchor_text": ANCHOR}
        )
        print(f"Status: {res.status_code}")
        print(f"Headers: {res.headers}")
        print(f"Content: {res.text[:200]}")
        
        if res.status_code != 200:
            print("FAIL: Locate endpoint returned non-200")
            print(res.text)
            return
            
        try:
            data = res.json()
            print(f"JSON: {data}")
        except:
             print("FAIL: Response is not JSON")
             
    except Exception as e:
        print(f"Error calling locate: {e}")

def test_stream():
    print(f"\nTesting GET /documents/{DOC_ID}/pages/17/stream with anchor...")
    try:
        res = requests.get(
            f"{API_URL}/knowledge/documents/{DOC_ID}/pages/17/stream",
            params={"anchor_text": ANCHOR},
            stream=True
        )
        print(f"Status: {res.status_code}")
        print(f"Headers: {res.headers}")
        # Peek at content type
        ctype = res.headers.get("Content-Type", "")
        print(f"Content-Type: {ctype}")
        
        if res.status_code != 200:
             print("FAIL: Stream returned non-200")
             print(res.text[:500])
        elif "application/pdf" not in ctype:
             print("FAIL: Did not return PDF")
             print(res.content[:200])
        else:
             print("SUCCESS: Stream returned PDF")
             
    except Exception as e:
        print(f"Error calling stream: {e}")

if __name__ == "__main__":
    test_locate()
    test_stream()
