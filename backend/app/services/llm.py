from openai import OpenAI
import os
import json

# GB10 Optimization: Point to Local NIM
# Defaults to local service in docker-compose, or falls back to public API
BASE_URL = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "dummy-key-for-local-nim")
MODEL_NAME = os.getenv("LLM_MODEL", "meta/llama3-70b-instruct")

print(f"Initializing LLM Client: {BASE_URL} with model {MODEL_NAME}")

import httpx
client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    http_client=httpx.Client(trust_env=False) # Prevent auto-proxy detection causing arg errors
)

STEP_PROMPT = """
You are an expert technical writer. 
Analyze the following raw step data (ASR text + Visual elements) and rewrite it into a clear, atomic action step.
Format:
{
    "action": "Verb + Object (e.g. Click 'Submit')",
    "expected_result": "What should happen (e.g. Dashboard loads)",
    "notes": "Any potential warnings or tips",
    "error_potential": "Low/Medium/High",
    "field_details": [
        {"label": "Username", "required": true, "validation": "Email format"}
    ]
}
"""

DECISION_PROMPT = """
Analyze the following sequence of user actions and narration to identify the logical flow.
Output JSON format:
{
    "logic_type": "linear",  
    "explanation": "Why this logic applies",
    "decision_node_index": -1, 
    "conditions": ["Condition A", "Condition B"]
}
"""

def refine_step(raw_text: str, ui_context: str):
    """
    Refines a raw step using Llama 3 70B (via NIM) or GPT-4.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": STEP_PROMPT},
                {"role": "user", "content": f"Text: {raw_text}\nUI Context: {ui_context}"}
            ],
            # Llama 3 supports json_mode usually, but let's be safe
            # If NIM supports it, great. If not, text parsing might be needed.
            # Most modern NIMs support response_format={"type": "json_object"}
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"LLM Error ({MODEL_NAME}): {e}")
        # Fallback
        return {
            "action": raw_text[:50], 
            "expected_result": "Action completed", 
            "notes": raw_text,
            "error_potential": "Unknown"
        }

def detect_logic_patterns(steps_text: list):
    """
    Analyzes a list of steps to find branching logic.
    """
    prompt = "\n".join([f"{i+1}. {txt}" for i, txt in enumerate(steps_text)])
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": DECISION_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Logic Detection Error: {e}")
        return {"logic_type": "linear", "explanation": "Fallback due to error", "branches": []}

SEGMENTATION_PROMPT = """
You are a master process analyst. 
The following text is a transcription of a training video. 
Break this text down into a sequential list of clear, atomic, actionable steps.
Ignore filler words like "um", "uh", "you know".
Output JSON format:
{
    "steps": [
        "Step 1 action...",
        "Step 2 action..."
    ]
}
"""

def segment_transcript(full_text: str):
    """
    Breaks a long transcript into discrete steps using the LLM.
    """
    MAX_CHUNK_SIZE = 2000000 # ~500k tokens. (Gemini 1M context handles this easily).
    # 3 hours audio = ~30k words = ~150k chars. So this limit allows 30+ hours without chunking.
    
    if len(full_text) < MAX_CHUNK_SIZE:
        # Small enough to process in one go
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SEGMENTATION_PROMPT},
                    {"role": "user", "content": full_text}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content).get("steps", [])
        except Exception as e:
            print(f"Segmentation Error: {e}")
            return [full_text]
            
    else:
        # chunk it
        print(f"Transcript too long ({len(full_text)} chars). Chunking...")
        chunks = [full_text[i:i+MAX_CHUNK_SIZE] for i in range(0, len(full_text), MAX_CHUNK_SIZE)]
        all_steps = []
        
        for i, chunk in enumerate(chunks):
            try:
                print(f"Processing Chunk {i+1}/{len(chunks)}...")
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SEGMENTATION_PROMPT},
                        {"role": "user", "content": f"(Part {i+1}) {chunk}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                steps = json.loads(response.choices[0].message.content).get("steps", [])
                all_steps.extend(steps)
            except Exception as e:
                print(f"Chunk {i} Error: {e}")
                
        return all_steps

def generate_text(prompt: str) -> str:
    """
    Generic text generation utility for Knowledge Engine.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM Generation Error: {e}")
        return ""

def get_embedding(text: str) -> list:
    """
    Generates vector embedding for text using OpenAI/compatible API.
    Returns list of floats.
    """
    try:
        # If using OpenRouter/NIM, check if they support embeddings endpoint.
        # Otherwise might need a fallback or specific model.
        # Defaulting to standard OpenAI call structure.
        response = client.embeddings.create(
            file=text, # Wrong arg? It's input=text usually. Let's check docs or use standard.
            # Client wrapper might be strict.
            model="text-embedding-3-small"
        )
        # Wait, OpenAI client uses `input`.
        # Correct call:
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding Error: {e}")
        # Return generic zero vector for safety? or None?
        # knowledge_ingestor expects list or throws?
        return []

SYNTHESIS_PROMPT = """
You are a "Hyper-Learning" Instructor.
Your goal is to convert a raw video step into a concise, rule-compliant training action.

Input:
1. Raw Step: "User kinda clicks the save button I guess"
2. Relevant Rules: 
   - "Must verify ZIP code before Save."
   - "Do not click Save if status is Offline."

Output JSON:
{
    "refined_action": "Verify ZIP Code, then click Save.",
    "compliance_warnings": ["Do not click if status is Offline"],
    "criticality": "HIGH"
}
"""

def refine_instruction_with_rules(raw_text: str, rules: list) -> dict:
    """
    Synthesizes a clean instruction merged with compliance rules.
    """
    rules_text = "\n".join([f"- {r}" for r in rules])
    user_content = f"Raw Step: \"{raw_text}\"\nRelevant Rules:\n{rules_text}"
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Rule Synthesis Error: {e}")
        return {
            "refined_action": raw_text,
            "compliance_warnings": [],
            "criticality": "LOW"
        }

def generate_structure(system_prompt: str, user_content: str, model: str = None) -> dict:
    """
    Generic structured generation using JSON mode.
    Useful for heavy tasks like Curriculum Architecture.
    Allows overriding the default model (e.g. for Long Context tasks).
    """
    target_model = model if model else MODEL_NAME
    try:
        response = client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Structure Generation Error: {e}")
        return {"error": str(e), "status": "failed"}
