import requests
import sys

def check_api():
    try:
        r = requests.get("http://localhost:8000/api/curriculum/videos")
        print(f"Status: {r.status_code}")
        print(f"Content Length: {len(r.content)} bytes")
        data = r.json()
        print(f"Item Count: {len(data)}")
        if len(data) > 0:
            print("First Item Keys:", data[0].keys())
            print("First Item ID:", data[0].get("id"))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_api()
