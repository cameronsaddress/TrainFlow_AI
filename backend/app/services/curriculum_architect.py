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
        return execute_map_reduce_strategy(db, videos, context_rules)

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

    # Phase 4: Enrich (Even for Direct Strategy)
    result_json = enrich_curriculum_with_knowledge(result_json, db)

    # 3. Persist to DB
    new_curriculum = k_models.TrainingCurriculum(
        title=result_json.get("course_title", "Untitled Course"),
        structured_json=result_json
    )
    db.add(new_curriculum)
    db.commit()
    db.refresh(new_curriculum)
    
    return {"id": new_curriculum.id, "result": result_json}

def execute_map_reduce_strategy(db: Session, videos: list, rules: str) -> dict:
    """
    Scalable Course Generation:
    1. Map: Summarize each video (if not already cached).
    2. Reduce: Create Master Plan from summaries.
    3. Detail: Expand each module with full context.
    """
    print("--- Phase 1: Summary Map ---", flush=True)
    summaries = []
    
    for v in videos:
        # Check cache in metadata_json
        meta = v.metadata_json or {}
        summary = meta.get("summary")
        
        if not summary:
            print(f"Summarizing {v.filename}...", flush=True)
            try:
                summary = summarize_video_content(v)
                # Store in DB
                meta["summary"] = summary
                v.metadata_json = meta
                db.commit()
            except Exception as e:
                print(f"Error summarizing {v.filename}: {e}")
                summary = f"Error summarizing video: {v.filename}"
        else:
            print(f"Using Cached Summary for {v.filename}", flush=True)
            
        summaries.append(f"<VIDEO_SUMMARY filename='{v.filename}'>\n{summary}\n</VIDEO_SUMMARY>")
    
    full_summary_context = "\n".join(summaries)
    
    print("--- Phase 2: Master Plan Reduce ---", flush=True)
    master_plan = generate_master_plan(full_summary_context, rules)
    print(f"Master Plan Generated: {len(master_plan.get('modules', []))} Modules", flush=True)
    
    print("--- Phase 3: Detail Expansion ---", flush=True)
    final_modules = []
    
    for module in master_plan.get("modules", []):
        print(f"Expansing Module: {module.get('title')}...", flush=True)
        
        # Determine context for this module
        source_filenames = module.get("recommended_source_videos", [])
        module_videos = [v for v in videos if v.filename in source_filenames]
        
        if not module_videos:
             print("No specific source video cited for module, using all summaries context for detail (fallback).")
             module_context = full_summary_context
        else:
             module_context = build_full_context(module_videos)
             
        detailed_module = generate_detailed_module(module, module_context)
        final_modules.append(detailed_module)
        
    master_plan["modules"] = final_modules
    
    # Phase 4: Enrich
    master_plan = enrich_curriculum_with_knowledge(master_plan, db)

    # Persist
    new_curriculum = k_models.TrainingCurriculum(
        title=master_plan.get("course_title", "Untitled Course"),
        structured_json=master_plan
    )
    db.add(new_curriculum)
    db.commit()
    db.refresh(new_curriculum)
    
    return {"id": new_curriculum.id, "result": master_plan}

def summarize_video_content(video) -> str:
    """
    Phase 1: Compress Video Context
    """
    raw_context = build_full_context([video])
    
    prompt = f"""
    Analyze this raw video data and generate a detailed Technical Summary (approx 500-1000 words).
    Focus on:
    1. The core procedure being demonstrated.
    2. Key steps performed.
    3. Systems/Tools used.
    4. Any safety warnings or compliance rules mentioned.
    
    Raw Data:
    {raw_context[:MAX_DIRECT_CONTEXT_CHARS]} 
    (Truncated safety limit applied if huge)
    """
    
    return llm.generate_text_simple(prompt)

def generate_master_plan(summary_context: str, rules: str) -> dict:
    """
    Phase 2: Master Skeleton
    """
    prompt = f"""
    You are the Curriculum Architect.
    {rules}
    
    Review these Video Summaries and design a Complete Course Structure.
    Target Audience: New Employees.
    
    Requirements:
    1. Organize the course such that **Each Module corresponds to exactly ONE Video**.
    2. The Module Title should reflect the Video's topic.
    3. You must sequence the Modules logically (e.g. foundational videos first).
    4. For each Module, you MUST strictly set "recommended_source_videos": ["exact_filename.mp4"].
    
    Output JSON format:
    {{
      "course_title": "...",
      "course_description": "...",
      "modules": [
        {{
           "title": "Module 1: [Topic from Video A]", 
           "recommended_source_videos": ["video_A.mp4"],
           "lessons": [] 
        }}
      ]
    }}
    
    Video Summaries:
    {summary_context}
    """
    return llm.generate_structure(
        system_prompt="You are an expert Instructional Designer.",
        user_content=prompt,
        model="x-ai/grok-4.1-fast" 
    )

def generate_detailed_module(module_skeleton: dict, context_str: str) -> dict:
    """
    Phase 3: Deep Dive
    """
    prompt = f"""
    You are the Content Developer.
    We are detailing the Module: "{module_skeleton.get('title')}".
    
    Context Data (Transcripts/OCR):
    {context_str}
    
    Task:
    1. Create detailed Lessons for this module based on the Context.
    2. You MUST define "source_clips" with start/end timestamps found in the Context.
    3. Verify timestamps exist.
    
    Output JSON (Module Object only):
    {{
        "title": "...",
        "lessons": [ ... (full lesson structure with voiceover_script and source_clips) ... ]
    }}
    """
    
    return llm.generate_structure(
        system_prompt="You are a meticulous content developer. Focus on timestamp accuracy.",
        user_content=prompt,
        model="x-ai/grok-4.1-fast"
    )

def enrich_curriculum_with_knowledge(curriculum_data: dict, db: Session = None) -> dict:
    """
    Phase 4: Knowledge Enrichment (The "Smart Assist" Layer)
    
    Iterates through the generated curriculum and injects "Just-in-Time" context 
    from the RAG Knowledge Base directly into the lesson structure.
    
    This runs at GENERATION TIME to avoid runtime latency.
    """
    print("--- Phase 4: Knowledge Enrichment (Smart Assist) ---", flush=True)
    
    # Pre-fetch Global Context (Rules/Glossary) to save tokens?
    # Actually, let's let the LLM decide relevance based on the script.
    # Ideally, we would vector search here.
    # For now, we will use a purely generative approach with Gemini Flash relative to the "Rules" context we already have.
    # If we had a Vector DB active, we would query it here.
    
    modules = curriculum_data.get("modules", [])
    total_lessons = sum(len(m.get("lessons", [])) for m in modules)
    print(f"Enriching {total_lessons} lessons with Contextual Guardrails...", flush=True)

    enriched_modules = []
    
    for module in modules:
        enriched_lessons = []
        for lesson in module.get("lessons", []):
            script = lesson.get("voiceover_script", "")
            if not script:
                enriched_lessons.append(lesson)
                continue
                
            # The "Deep Search" / Synthesis Step
            try:
                # We ask Gemini to hallucinations "safe" generic advice if it doesn't have specific vectors yet,
                # BUT since we passed "rules" earlier to the Architect, we can assume some rule context is known.
                # However, to be robust, let's pretend we are doing a "Pass 2" analysis.
                
                context_prompt = f"""
                Analyze this Training Script and generate "Smart Assist" metadata.
                
                Script: "{script}"
                
                Identify:
                1. "compliance_rules": Any strict DOs/DON'Ts implied (e.g. "Must save", "Never skip").
                2. "troubleshooting_tips": Common errors a user might face here.
                3. "related_topics": Keywords to link to documentation.
                
                Output JSON:
                {{
                   "compliance_rules": [ {{ "trigger": "Action", "rule": "..." }} ],
                   "troubleshooting_tips": [ {{ "issue": "...", "fix": "..." }} ],
                   "related_topics": ["..."]
                }}
                """
                
                smart_context = llm.generate_structure(
                    system_prompt="You are a Compliance & Support AI. Extract actionable guardrails.",
                    user_content=context_prompt,
                    model="x-ai/grok-4.1-fast" # Generation Time: One-time Grok Call
                )
                
                lesson["smart_context"] = smart_context
                
            except Exception as e:
                print(f"Failed to enrich lesson '{lesson.get('title')}': {e}", flush=True)
                lesson["smart_context"] = {} # Fallback
                
            enriched_lessons.append(lesson)
        
        module["lessons"] = enriched_lessons
        enriched_modules.append(module)
        
    curriculum_data["modules"] = enriched_modules
    return curriculum_data

