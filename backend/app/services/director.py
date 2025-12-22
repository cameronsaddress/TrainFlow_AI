import json
from .llm import client, MODEL_NAME

DIRECTOR_PROMPT = """
You are an expert Instructional Designer and Video Editor.
Your goal is to remix raw footage into a high-impact "Director's Cut" training video.
You have access to:
1.  **Speech (ASR)**: What was said.
2.  **Screen (OCR)**: What was shown (slides, menus, error messages).

OBJECTIVE: Create the "Perfect Cut" - Concise, Logical, Complete.
-   **ALL CONTENT**: You MUST maximize the retention of informational content (Speech + OCR).
-   **CONCISE**: Remove repetitive actions or non-informational "dead air".
-   **PACING**: Trim any silence longer than 3 seconds unless it's a critical reading pause for a complex slide.
-   **LOGIC**: Re-order steps ONLY if the raw footage is out of sequence. Ensure linear, logical flow.

Input: List of Steps (index, text (speech), ocr (screen), duration).
Output: JSON with "curated_indices": [{ "original_index": int, "overlay_text": string }]

"overlay_text" guidelines:
-   Action-Oriented (e.g., "Review Safety Rules", "Click Submit").
-   Max 6 words.
-   use the OCR text to create the most accurate overlay.
"""

def curate_steps(raw_steps: list) -> list:
    """
    Uses LLM to select best steps and rewrite overlays.
    raw_steps: List of dicts with 'action_details', 'duration', 'step_number'
    Returns: List of dicts {original_index, overlay_text}
    """
    
    # Minimize token usage by sending only essential fields
    simplified_input = []
    for i, s in enumerate(raw_steps):
        simplified_input.append({
            "index": i,
            "text": s.get('action_details', '')[:200], # Speech
            "ocr": s.get('ocr_context', '')[:500],   # Screen (New!)
            "duration": f"{s.get('duration', 0):.1f}s"
        })
        
    prompt_content = json.dumps(simplified_input, indent=2)
    
    try:
        print(f"Director Curating {len(raw_steps)} steps...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": DIRECTOR_PROMPT},
                {"role": "user", "content": f"Raw Footage:\n{prompt_content}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2 # Low temp for strict adherence
        )
        
        result = json.loads(response.choices[0].message.content)
        curated = result.get("curated_indices", [])
        
        print(f"Director selected {len(curated)}/{len(raw_steps)} steps.")
        return curated
        
    except Exception as e:
        print(f"Director Failed (Fallback to Linear): {e}")
        # Fallback: Keep all, use raw text as overlay
        fallback = []
        for i, s in enumerate(raw_steps):
            fallback.append({
                "original_index": i,
                "overlay_text": s.get('action_details', '')[:30] # Simple truncate
            })
        return fallback
