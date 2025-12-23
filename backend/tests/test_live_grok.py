import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))
# Docker path compliance
if os.path.exists("/app/app"):
    sys.path.append("/app")

from app.services import llm

def test_live_grok():
    print("Testing Live Connection to x-ai/grok-4.1-fast...")
    try:
        response = llm.generate_structure(
            system_prompt="You are a test bot.", 
            user_content="Return JSON: {'status': 'online'}",
            model="x-ai/grok-4.1-fast"
        )
        print(f"LIVE RESPONSE: {response}")
    except Exception as e:
        print(f"CONNECTION FAILED: {e}")

if __name__ == "__main__":
    test_live_grok()
