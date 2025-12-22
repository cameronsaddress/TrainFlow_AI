import json
from PIL import Image
import io
from sqlalchemy.orm import Session
from ..models.models import Video
from .llm import client

# Explicitly use Gemini 3 Flash Preview as requested
VISION_MODEL = "google/gemini-3-flash-preview"

FIELD_ASSISTANT_PROMPT = """
You are an expert Utility Pole Inspector and Foreman.
Analyze the provided image for structural defects, safety hazards, or maintenance needs.

CONTEXT:
1. Use the following "Context Rules" extracted from our training manuals (Transcripts):
{rules}
2. **CRITICAL**: You are NOT limited to these rules. Use your extensive general knowledge of utility infrastructure (NESC standards) to identify ANY other issues.

INSTRUCTIONS:
1. **Identify COMPREHENSIVE Defects**: Find *everything* wrong (Structural, Electrical, Vegetation, Safety).
2. **Draw Bounding Box**: You MUST provide a Bounding Box [ymin, xmin, ymax, xmax] (0-1000 scale) for EVERY issue.
3. **Repair Action**: Map "Why/What to do" for each issue.
4. **Pole Summary**: Provide a detailed summary of the pole's setup, equipment, and general condition for the Corporate Office.

Output JSON format:
{{
    "pole_summary": "This is a Class 40 Wood Pole carrying 12kV distribution lines with a transformer bank...",
    "defects": [
        {{
            "label": "Woodpecker Role",
            "box_2d": [ymin, xmin, ymax, xmax],
            "severity": "Critical",
            "repair_action": "Fill with resin..."
        }}
    ]
}}
"""

def analyze_pole_image(file_bytes: bytes, db: Session):
    # 1. Retrieve RAG Context (Naive)
    # Fetch all logs and simple text search for relevant "Rules"
    # Optimization: In prod, use Vector DB. Here, linear scan of recent 5 videos is fine for demo.
    videos = db.query(Video).order_by(Video.created_at.desc()).limit(5).all()
    
    rules_context = []
    keywords = ["repair", "replace", "install", "check", "danger", "verify"]
    
    for v in videos:
        if v.transcription_log:
            # transcription_log is list of steps. flatten to text.
            for step in v.transcription_log:
                text = step.get('action_details', '')
                if any(k in text.lower() for k in keywords):
                    rules_context.append(f"- {text}")
                    
    # Deduplicate and limit context length
    rules_text = "\n".join(list(set(rules_context))[:20]) 
    
    if not rules_text:
        rules_text = "Standard Utility Pole Maintenance Standards apply."

    # 2. Call Vision Model
    # Gemini 2.0 Flash accepts image inputs
    import base64
    img_b64 = base64.b64encode(file_bytes).decode('utf-8')
    
    import re
    import traceback

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": FIELD_ASSISTANT_PROMPT.format(rules=rules_text)},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this pole image."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        raw_content = response.choices[0].message.content
        print(f"DEBUG: LLM Raw Content:\n{raw_content}")

        # Robust JSON Extraction
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if match:
             json_str = match.group(0)
             return json.loads(json_str)
        else:
             print("DEBUG: No JSON found in output")
             return {"defects": [], "error": "Model returned invalid format"}

    except Exception as e:
        print(f"Field Assistant Error: {e}")
        traceback.print_exc()
        return {"defects": [], "error": str(e)}
