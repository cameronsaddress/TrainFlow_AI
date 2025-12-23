import sys
import os
import json
from unittest.mock import MagicMock, patch

# Add backend to path
import sys
import os
# If running in Docker /app, add it. If running locally, add ../backend
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # Should be /app or .../backend
sys.path.append(parent_dir)

from app.models import knowledge as k_models
from app.services import curriculum_architect

def test_curriculum_generation():
    print("Verifying Curriculum Architect...")
    
    # 1. Mock DB Session
    mock_db = MagicMock()
    
    # 2. Mock Video Data (Small enough for Direct Strategy)
    mock_video = k_models.VideoCorpus(
        id=1,
        filename="training_demo.mp4",
        duration_seconds=600.0,
        status=k_models.DocStatus.READY,
        transcript_text="Welcome to the training.",
        transcript_json={
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Welcome to the training."},
                {"start": 5.1, "end": 10.0, "text": "Click the login button."}
            ]
        },
        ocr_json=[
            {"timestamp": 5.5, "text": "Login Screen"},
            {"timestamp": 6.0, "text": "Username Field"}
        ]
    )
    
    # Mock Query Return
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_video]
    
    # 3. Mock LLM Response
    mock_response = {
        "course_title": "Mock Course",
        "modules": []
    }
    
    with patch("app.services.llm.generate_structure", return_value=mock_response) as mock_llm:
        # Run
        result = curriculum_architect.generate_curriculum(mock_db)
        
        # Verify
        print(f"Result: {result}")
        
        # Check Strategy Selection logic (Should be Direct)
        if mock_llm.called:
            args = mock_llm.call_args
            print("LLM Called Successfully.")
            # Verify Prompt content contains video info
            user_content = args[1]['user_content']
            if "training_demo.mp4" in user_content:
                print("SUCCESS: Context data found in Prompt.")
            else:
                print("FAILURE: Video data missing from Prompt.")
                
            if "Login Screen" in user_content:
                 print("SUCCESS: OCR data found in Prompt.")
            else:
                 print("FAILURE: OCR data missing from Prompt.")
                 
            # Verify Model Override
            model_arg = args[1].get('model')
            if model_arg == "x-ai/grok-4.1-fast":
                print("SUCCESS: Model override correctly requested Grok 4.1.")
            else:
                print(f"FAILURE: Model override mismatch: {model_arg}")
        else:
            print("FAILURE: LLM was not called.")

if __name__ == "__main__":
    test_curriculum_generation()
