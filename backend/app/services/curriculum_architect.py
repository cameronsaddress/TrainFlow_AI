import json
import logging
from sqlalchemy.orm import Session
from ..models import knowledge as k_models
from . import llm

logger = logging.getLogger(__name__)

# Heuristic: 1 token ~= 4 chars (English)
# Gemini Flash 3 limit: 1,000,000 tokens ~= 4,000,000 chars
# We set a safe limit of 800k tokens (3.2M chars) to allow for prompt overhead.
MAX_DIRECT_CONTEXT_CHARS = 3200000 

INSTRUCTIONAL_DESIGNER_PROMPT = """
You are a World-Class Instructional Designer and Technical Writer.
Your goal is to analyze a corpus of raw video data (transcripts and OCR screen reads) and design a comprehensive "Hyper-Learning" Course.

# The Data
You will receive raw data from multiple video files.
For each video, you have:
1. "transcript_json": A word-by-word timeline of spoken audio.
2. "ocr_json": Periodic screen text captures with timestamps.

# Your Task
Create a structured JSON Course Plan.
The course should be broken down into logical Modules and Lessons.
CRITICAL: For every lesson, you must define the "source_clips" - the exact segments of video that demonstrate the concept.
You MUST VALIDATE that the timestamps you cite actually exist in the source video data.

# Output Format
{
  "course_title": "Mastering the [Topic]",
  "course_description": "...",
  "modules": [
    {
      "title": "Module 1: ...",
      "lessons": [
        {
          "title": "Lesson 1.1: [Action-Oriented Title]",
          "learning_objective": "User will be able to...",
          "voiceover_script": "A concise, professional script summarizing the action...",
          "source_clips": [
            {
               "video_filename": "exact_filename_from_data.mp4",
               "start_time": 10.5,
               "end_time": 45.0,
               "reason": "Shows the user navigating the menu."
            }
          ]
        }
      ]
    }
  ]
}
"""

def generate_curriculum(db: Session, context_rules: str = "") -> dict:
    """
    The Brain: Aggregates all READY videos and generates a course structure.
    Uses Hybrid Strategy: Direct Ingestion vs Map-Reduce.
    """
    # 1. Fetch All Ready Videos
    videos = db.query(k_models.VideoCorpus).filter(
        k_models.VideoCorpus.status == k_models.DocStatus.READY
    ).all()
    
    if not videos:
        return {"error": "No READY videos found in corpus."}
        
    print(f"Curriculum Architect: Analyzing {len(videos)} videos...", flush=True)
    
    # 2. Build Context Payload
    full_context_str = build_full_context(videos)
    total_chars = len(full_context_str)
    
    print(f"Total Context Size: {total_chars} chars (~{total_chars/4:.0f} tokens)", flush=True)
    
    # 3. Select Strategy
    if total_chars < 3200000: # ~800k tokens (Safe for 1M window)
        print("Strategy: DIRECT INGESTION (Context fits in 1M window)", flush=True)
        return execute_direct_strategy(db, full_context_str, context_rules)
    else:
        print("Strategy: MAP-REDUCE (Context too large, summarizing first)", flush=True)
        return execute_map_reduce_strategy(videos, context_rules)

def build_full_context(videos: list) -> str:
    """
    Concatenates all video data into a single XML-like string.
    """
    context_parts = []
    
    for video in videos:
        # Transcript Logic:
        # Ideally we use the JSON timeline for precision, but it can be huge.
        # For the Prompt, a readable format with timestamps is best.
        # Let's create a "Dense Log" format.
        
        dense_log = f"<VIDEO filename='{video.filename}' duration='{video.duration_seconds}'>\n"
        
        # 1. Add Transcript Segments (if available in JSON)
        # We prefer the raw JSON if available to get word-level precision, 
        # but to save tokens, we might group by 5-10 second chunks.
        # For now, let's use the full text but maybe we should rely on the timeline if possible.
        # Actually, let's just dump the raw Transcript Text first, but we need timestamps.
        # If transcript_json exists, we reconstruct a "Timestamped Script".
        
        if video.transcript_json:
            timeline = video.transcript_json.get("segments", []) 
            # Note: ASR 'segments' usually have 'start', 'end', 'text'.
            # ASR 'timeline' has word-level.
            # We used 'segments' in asr.py return for the high level chunks.
            
            if not timeline and video.transcript_text:
                 # Fallback to mostly text if segments missing
                 dense_log += f"<TRANSCRIPT>\n{video.transcript_text}\n</TRANSCRIPT>\n"
            else:
                dense_log += "<TRANSCRIPT_TIMELINE>\n"
                for seg in timeline:
                    start = seg.get('start', 0)
                    end = seg.get('end', 0)
                    text = seg.get('text', '')
                    dense_log += f"[{start:.2f}-{end:.2f}] {text}\n"
                dense_log += "</TRANSCRIPT_TIMELINE>\n"
        
        # 2. Add OCR Events
        if video.ocr_json:
             dense_log += "<ON_SCREEN_TEXT>\n"
             # ocr_json is list of {timestamp, text_content}
             for item in video.ocr_json:
                 ts = item.get('timestamp')
                 txt = item.get('text', '')
                 # Filter trivial text to save tokens?
                 if len(txt) > 5: 
                     dense_log += f"[{ts:.2f}s] {txt}\n"
             dense_log += "</ON_SCREEN_TEXT>\n"
             
        dense_log += "</VIDEO>\n"
        context_parts.append(dense_log)
        
    return "\n".join(context_parts)

def execute_direct_strategy(db: Session, context_str: str, rules: str):
    """
    Single-shot generation using the massive context.
    """
    # We can override model here if we want to ensure Flash 3 is used.
    # For now, we trust the env var or default, but we should likely 
    # allow 'google/gemini-flash-1.5-8b' or similar if configured.
    
    user_message = f"""
    {rules}
    
    Here is the Raw Video Data:
    {context_str}
    
    Generate the Course Plan now.
    """
    
    result_json = llm.generate_structure(
        system_prompt=INSTRUCTIONAL_DESIGNER_PROMPT, 
        user_content=user_message,
        model="x-ai/grok-4.1-fast" # Explicitly request high-context model if available
    )

    # 3. Persist to DB
    new_curriculum = k_models.TrainingCurriculum(
        title=result_json.get("course_title", "Untitled Course"),
        structured_json=result_json
    )
    db.add(new_curriculum)
    db.commit()
    db.refresh(new_curriculum)
    
    return {"id": new_curriculum.id, "result": result_json}

def execute_map_reduce_strategy(videos: list, rules: str):
    """
    Fallback: Summarize each video first, then generate plan.
    (Placeholder for V2)
    """
    return {"error": "Map-Reduce Strategy not yet implemented. Corpus too large for Direct strategy."}
