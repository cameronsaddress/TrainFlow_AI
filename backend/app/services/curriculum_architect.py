import json
import logging
import asyncio
from sqlalchemy.orm import Session
from ..models import knowledge as k_models
from ..schemas.curriculum import Module
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

async def generate_curriculum(db: Session, context_rules: str = ""):
    """
    The Brain: Aggregates all READY videos and generates a course structure (Async).
    Uses Hybrid Strategy: Direct Ingestion vs Map-Reduce.
    YIELDS: Status strings (str) OR Final Dictionary (dict)
    """
    # 1. Fetch All Ready Videos
    yield "Scanning Video Corpus..."
    # DB calls are sync, but fast enough to block briefly. 
    # Logic remains strict sync for DB, async for LLM.
    videos = db.query(k_models.VideoCorpus).filter(
        k_models.VideoCorpus.status == k_models.DocStatus.READY
    ).all()
    
    if not videos:
        yield {"error": "No READY videos found in corpus."}
        return
        
    yield f"Curriculum Architect: Analyzing {len(videos)} videos..."
    print(f"Curriculum Architect: Analyzing {len(videos)} videos...", flush=True)
    
    # 2. Build Context Payload
    full_context_str = build_full_context(videos)
    total_chars = len(full_context_str)
    
    print(f"Total Context Size: {total_chars} chars (~{total_chars/4:.0f} tokens)", flush=True)
    yield f"Context Window: {total_chars:,} chars. Selecting AI Strategy..."
    
    # 3. Select Strategy
    if total_chars < 3200000: # ~800k tokens (Safe for 1M window)
        print("Strategy: DIRECT INGESTION (Context fits in 1M window)", flush=True)
        yield "Strategy: Direct Context Ingestion. Architecting Course..."
        
        # Iterate Direct Strategy Generator
        async for status in execute_direct_strategy(db, full_context_str, context_rules):
            yield status
            
    else:
        print("Strategy: MAP-REDUCE (Context too large, summarizing first)", flush=True)
        yield "Strategy: Map-Reduce (Large Context). Summarizing footage..."
        
        # Iterate Map-Reduce Strategy Generator
        async for status in execute_map_reduce_strategy(db, videos, context_rules):
            yield status
            
    # Note: Phase 4 is now inside the strategies, so we are done.
    # The last yielded item from the strategies is the Result Dict.
    return

def build_full_context(videos: list) -> str:
    """
    Concatenates all video data into a single XML-like string.
    """
    context_parts = []
    
    for video in videos:
        dense_log = f"<VIDEO filename='{video.filename}' duration='{video.duration_seconds}'>\n"
        
        if video.transcript_json:
            timeline = video.transcript_json.get("segments", []) 
            if not timeline and video.transcript_text:
                 dense_log += f"<TRANSCRIPT>\n{video.transcript_text}\n</TRANSCRIPT>\n"
            else:
                dense_log += "<TRANSCRIPT_TIMELINE>\n"
                for seg in timeline:
                    start = seg.get('start', 0)
                    end = seg.get('end', 0)
                    text = seg.get('text', '')
                    dense_log += f"[{start:.2f}-{end:.2f}] {text}\n"
                dense_log += "</TRANSCRIPT_TIMELINE>\n"
        
        if video.ocr_json:
             dense_log += "<ON_SCREEN_TEXT>\n"
             for item in video.ocr_json:
                 ts = item.get('timestamp')
                 txt = item.get('text', '')
                 if len(txt) > 5: 
                     dense_log += f"[{ts:.2f}s] {txt}\n"
             dense_log += "</ON_SCREEN_TEXT>\n"
             
        dense_log += "</VIDEO>\n"
        context_parts.append(dense_log)
        
    return "\n".join(context_parts)

async def execute_direct_strategy(db: Session, full_context_str: str, context_rules: str = ""):
    """
    Direct Ingestion Strategy (Streaming)
    """
    user_message = f"""
    Context Data:
    {full_context_str}
    
    Generate the Course Plan now.
    """
    
    yield "Phase 2: Direct Architecture Generation..."
    result_json = await llm.generate_structure(
        system_prompt=INSTRUCTIONAL_DESIGNER_PROMPT, 
        user_content=user_message,
        model="x-ai/grok-4.1-fast" 
    )

    # Phase 4: Enrich (Streamed)
    if "modules" in result_json:
        async for status in enrich_curriculum_generator(result_json, db):
            yield status
            if isinstance(status, dict):
                 result_json = status
                 
    yield result_json

async def execute_map_reduce_strategy(db: Session, videos: list, rules: str):
    """
    Scalable Course Generation (Streaming):
    1. Map: Summarize each video (if not already cached).
    2. Reduce: Create Master Plan from summaries.
    3. Detail: Expand each module with full context.
    4. Enrich: Smart Assist.
    """
    print("--- Phase 1: Summary Map ---", flush=True)
    yield "Phase 1: Generating Video Summaries (Map)..."
    summaries = []
    
    for i, v in enumerate(videos):
        meta = v.metadata_json or {}
        summary = meta.get("summary")
        
        if not summary:
            print(f"Summarizing {v.filename}...", flush=True)
            yield f"Summarizing Video {i+1}/{len(videos)}: {v.filename}..."
            try:
                summary = await summarize_video_content(v)
                # Store in DB
                meta["summary"] = summary
                v.metadata_json = meta
                db.commit()
            except Exception as e:
                print(f"Error summarizing {v.filename}: {e}")
                summary = f"Error summarizing video: {v.filename}"
        else:
            print(f"Using Cached Summary for {v.filename}", flush=True)
            yield f"Using Cached Summary for {v.filename}..."
            
        summaries.append(f"<VIDEO_SUMMARY filename='{v.filename}'>\n{summary}\n</VIDEO_SUMMARY>")
    
    full_summary_context = "\n".join(summaries)
    
    print("--- Phase 2: Master Plan Reduce ---", flush=True)
    yield "Phase 2: Architecting Master Course Plan (Reduce)..."
    master_plan = await generate_master_plan(full_summary_context, rules)
    print(f"Master Plan Generated: {len(master_plan.get('modules', []))} Modules", flush=True)
    
    print("--- Phase 3: Detail Expansion ---", flush=True)
    yield f"Phase 3: Expanding {len(master_plan.get('modules', []))} Modules with Deep Context..."
    final_modules = []
    
    for i, module in enumerate(master_plan.get("modules", [])):
        print(f"Expanding Module: {module.get('title')}...", flush=True)
        yield f"Drafting Module {i+1}/{len(master_plan.get('modules', []))}: {module.get('title')}..."
        
        # Determine context for this module
        source_filenames = module.get("recommended_source_videos", [])
        module_videos = [v for v in videos if v.filename in source_filenames]
        
        if not module_videos:
             print("No specific source video cited for module, using GLOBAL SUMMARIES context for detail (fallback).", flush=True)
             module_context = full_summary_context
        else:
             module_context = build_full_context(module_videos)
             
        # Detect empty context (e.g. video has no transcripts)
        if not module_context or not module_context.strip():
             print("Specific context was empty. Falling back to GLOBAL SUMMARIES context.", flush=True)
             module_context = full_summary_context
             
        try:
            detailed_module = await generate_detailed_module_validated(module, module_context)
            final_modules.append(detailed_module)
            yield f"Completed Module {i+1}. Result: {len(detailed_module.get('lessons', []))} Lessons."
        except Exception as e:
            print(f"FAILED Expanding Module {i+1}: {e}")
            yield f"Failed Module {i+1}: {e}. Skipping temporarily."
            # We preserve the skeletons? Or just skip? 
            # If validated failed, let's keep the skeleton but mark as raw.
            module["error"] = str(e)
            final_modules.append(module)

    master_plan["modules"] = final_modules
    
    # Phase 4: Enrich
    async for status in enrich_curriculum_generator(master_plan, db):
        yield status
        if isinstance(status, dict):
             master_plan = status

    yield master_plan

async def summarize_video_content(video) -> str:
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
    
    return await llm.generate_text(prompt)

async def generate_master_plan(summary_context: str, rules: str) -> dict:
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
    return await llm.generate_structure(
        system_prompt="You are an expert Instructional Designer.",
        user_content=prompt,
        model="x-ai/grok-4.1-fast" 
    )

async def generate_detailed_module_validated(module_skeleton: dict, context_str: str) -> dict:
    """
    Phase 3: Deep Dive (Validated with Pydantic)
    Strategy:
    1. Try Standard Full-Context Generation.
    2. If fails (Context too large/JSON cutoff), Switch to "Split & Recombine" (Chunking).
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
        "title": "{module_skeleton.get('title')}",
        "lessons": [ ... (full lesson structure with voiceover_script and source_clips) ... ],
        "recommended_source_videos": {json.dumps(module_skeleton.get('recommended_source_videos', []))}
    }}
    """
    
    try:
        # Attempt 1: Standard
        module_model = await llm.generate_structure_validated(
            system_prompt="You are a meticulous content developer. Focus on timestamp accuracy and strict JSON structure.",
            user_content=prompt,
            model_class=Module,
            model="x-ai/grok-4.1-fast",
            max_retries=1 
        )
        # Validate content fidelity
        if not module_model.lessons or len(module_model.lessons) == 0:
            print("  ⚠️ Standard Generation produced 0 lessons. Treating as failure -> Switching to CHUNKING...", flush=True)
            return await generate_module_in_chunks(module_skeleton, context_str)
            
        return module_model.model_dump()
        
    except Exception as e:
        print(f"  ⚠️ Standard Generation Failed: {e}. Switching to SPLIT & RECOMBINE Strategy...", flush=True)
        return await generate_module_in_chunks(module_skeleton, context_str)

async def generate_module_in_chunks(module_skeleton: dict, context_str: str) -> dict:
    """
    Fidelity Fix: Splits massive context into chunks, generates lessons for each, and merges.
    """
    # 1. Split Context into Chunks
    # Simple overlap splitting
    CHUNK_SIZE = 100000 # 100k chars (~25k tokens)
    OVERLAP = 5000
    
    chunks = []
    start = 0
    while start < len(context_str):
        end = min(start + CHUNK_SIZE, len(context_str))
        chunk = context_str[start:end]
        chunks.append(chunk)
        if end == len(context_str):
            break
        start = end - OVERLAP
        
    print(f"  🔄 Splitting into {len(chunks)} chunks for High Fidelity...", flush=True)
    
    all_lessons = []
    
    for i, chunk in enumerate(chunks):
        print(f"  📝 Processing Chunk {i+1}/{len(chunks)}...", flush=True)
        chunk_prompt = f"""
        You are the Content Developer.
        We are detailing a SECTION of the Module: "{module_skeleton.get('title')}".
        
        PARTIAL Context Data (Part {i+1}/{len(chunks)}):
        {chunk}
        
        Task:
        1. Extract and create detailed Lessons FOUND ONLY IN THIS PARTIAL CONTEXT.
        2. Do not hallucinate lessons from other parts.
        3. Include "source_clips" with timestamps.
        
        Output JSON:
        {{
            "title": "{module_skeleton.get('title')} (Part {i+1})",
            "lessons": [ ... ]
        }}
        """
        
        try:
            partial_module = await llm.generate_structure_validated(
                system_prompt="You are a meticulous content developer. Extract lessons from this specific segment.",
                user_content=chunk_prompt,
                model_class=Module,
                model="x-ai/grok-4.1-fast"
            )
            all_lessons.extend(partial_module.lessons)
            
        except Exception as e:
            print(f"  ❌ Failed to process chunk {i+1}: {e}", flush=True)
            # Continue to next chunks to save what we can
            
    # Merge
    print(f"  ✅ Recombined {len(all_lessons)} lessons from {len(chunks)} chunks.", flush=True)
    return {
        "title": module_skeleton.get("title"),
        "lessons": [l.model_dump() for l in all_lessons],
        "recommended_source_videos": module_skeleton.get("recommended_source_videos", [])
    }

async def enrich_curriculum_generator(curriculum_data: dict, db: Session = None):
    """
    Phase 4: Knowledge Enrichment (Streaming Version)
    Yields status strings, then yields final enriched Dict.
    """
    print("--- Phase 4: Knowledge Enrichment (Smart Assist) ---", flush=True)
    yield "Phase 4: Starting Knowledge Enrichment..."
    
    modules = curriculum_data.get("modules", [])
    total_lessons = sum(len(m.get("lessons", [])) for m in modules)
    yield f"Smart Assist: Analyzing {total_lessons} Lessons for Compliance..."

    enriched_modules = []
    lesson_count = 0
    
    for module in modules:
        enriched_lessons = []
        for lesson in module.get("lessons", []):
            lesson_count += 1
            title = lesson.get("title", f"Lesson {lesson_count}")
            # yield f"Smart Assist: Analyzing Lesson {lesson_count}/{total_lessons}: {title}..."
            
            # Reduce verbosity slightly for UI
            if lesson_count % 3 == 0: 
               yield f"Smart Assist: Analyzing Lesson {lesson_count}/{total_lessons}..."

            script = lesson.get("voiceover_script", "")
            if not script:
                enriched_lessons.append(lesson)
                continue
                
            try:
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
                
                smart_context = await llm.generate_structure(
                    system_prompt="You are a Compliance & Support AI. Extract actionable guardrails.",
                    user_content=context_prompt,
                    model="x-ai/grok-4.1-fast"
                )
                
                lesson["smart_context"] = smart_context

                # --- QUIZ GENERATION ---
                quiz_prompt = f"""
                Based on the Lesson Script below, generate a multiple-choice quiz to test understanding.
                
                Script: "{script}"
                
                Requirements:
                1. Identify the most critical concepts.
                2. Create multiple-choice questions (max 15, but use fewer if appropriate).
                3. Provide 3-4 options per question.
                4. Indicate the correct answer and a brief explanation.
                
                Output JSON:
                {{
                  "questions": [
                    {{
                      "question": "...",
                      "options": ["Option A", "Option B", "Option C"],
                      "correct_answer": "Option A",
                      "explanation": "..."
                    }}
                  ]
                }}
                """
                
                quiz_data = await llm.generate_structure(
                    system_prompt="You are an Instructional Designer. Create a knowledge check quiz.",
                    user_content=quiz_prompt,
                    model="x-ai/grok-4.1-fast"
                )
                
                lesson["quiz"] = quiz_data
                
            except Exception as e:
                print(f"Failed to enrich lesson '{title}': {e}", flush=True)
                lesson["smart_context"] = {} # Fallback
                lesson["quiz"] = {} # Fallback
                
            enriched_lessons.append(lesson)
        
        module["lessons"] = enriched_lessons
        enriched_modules.append(module)
        
    curriculum_data["modules"] = enriched_modules
    yield "Enrichment Complete. Finalizing Course Plan..."
    yield curriculum_data
