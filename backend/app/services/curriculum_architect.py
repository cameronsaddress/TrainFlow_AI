import json
import logging
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
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
      "description": "A comprehensive overview of what this module covers...",
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
        k_models.VideoCorpus.status == k_models.DocStatus.READY,
        k_models.VideoCorpus.is_archived == False
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
    
    # 2.5 Identify Domain Context
    yield "Analyzing Training Domain (Persona, Student, Goal)..."
    detected_context = await detect_domain_context(videos)
    
    # 3. Select Strategy
    if total_chars < 3200000: # ~800k tokens (Safe for 1M window)
        print("Strategy: DIRECT INGESTION (Context fits in 1M window)", flush=True)
        yield "Strategy: Direct Context Ingestion. Architecting Course..."
        
        # Iterate Direct Strategy Generator
        async for status in execute_direct_strategy(db, full_context_str, context_rules, detected_context):
            yield status
            
    else:
        print("Strategy: MAP-REDUCE (Context too large, summarizing first)", flush=True)
        yield "Strategy: Map-Reduce (Large Context). Summarizing footage..."
        
        # Iterate Map-Reduce Strategy Generator
        async for status in execute_map_reduce_strategy(db, videos, context_rules, detected_context):
            yield status
            
    # Note: Phase 4 is now inside the strategies, so we are done.
    # The last yielded item from the strategies is the Result Dict.
    return

def save_curriculum_checkpoint(db: Session, curriculum_id: int, data: dict):
    """
    Updates the existing TrainingCurriculum record with the latest progress.
    """
    try:
        record = db.query(k_models.TrainingCurriculum).get(curriculum_id)
        if record:
            record.structured_json = data
            flag_modified(record, "structured_json")
            db.commit()
    except Exception as e:
        print(f"Failed to save checkpoint: {e}")



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

async def execute_direct_strategy(db: Session, full_context_str: str, context_rules: str = "", detected_context: dict = None):
    """
    Direct Ingestion Strategy (Streaming)
    """
    user_message = f"""
    Context Data:
    {full_context_str}
    
    Generate the Course Plan now.
    """
    
    # Phase 2: Direct Architecture Generation...
    yield "Phase 2: Direct Architecture Generation..."
    
    # Inject Context into Persona
    instructor = "Instructional Designer"
    domain_context_str = ""
    if detected_context:
        inst = detected_context.get("instructor_persona", "Instructor")
        stud = detected_context.get("student_persona", "Student")
        dom = detected_context.get("target_domain", "Subject")
        domain_context_str = f"\n    CONTEXT: You are a {inst} designing a course for {stud} about {dom}.\n"

    final_user_msg = f"""
    {domain_context_str}
    {user_message}
    """

    result_json = await llm.generate_structure(
        system_prompt=INSTRUCTIONAL_DESIGNER_PROMPT, 
        user_content=final_user_msg,
        model="x-ai/grok-4.1-fast" 
    )

    # PERSISTENCE: Save early
    curr_id = None
    try:
        new_plan = k_models.TrainingCurriculum(
            title=result_json.get("course_title", "Untitled Course"),
            structured_json=result_json
        )
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        curr_id = new_plan.id
        print(f"Created Curriculum ID {curr_id} (Direct Strategy)", flush=True)
    except Exception as e:
        print(f"Failed to create curriculum record: {e}")

    # Phase 4: Enrich (Streamed)
    if "modules" in result_json:
        # Pass Detected Context
        async for status in enrich_curriculum_generator(result_json, db, detected_context=detected_context, curriculum_id=curr_id):
            yield status
            if isinstance(status, dict):
                 result_json = status
                 
    yield result_json

async def execute_map_reduce_strategy(db: Session, videos: list, rules: str, detected_context: dict = None):
    """
    Scalable Course Generation (Streaming):
    1. Map: Summarize each video (if not already cached).
    2. Reduce: Create Master Plan from summaries.
    3. Detail: Expand each module with full context.
    4. Enrich: Smart Assist.
    """
    print("--- Phase 1: Summary Map (Parallel Swarm) ---", flush=True)
    yield "Phase 1: Generating Video Summaries (Swarm Mode)..."
    
    summaries = [None] * len(videos)
    sem = asyncio.Semaphore(10) # 10 Concurrent Summarizers

    async def summarize_worker(i, v):
        async with sem:
            meta = v.metadata_json or {}
            summary = meta.get("summary")
            
            if not summary:
                print(f"Summarizing {v.filename}...", flush=True)
                try:
                    summary = await summarize_video_content(v)
                    # Sync DB writing is risky in async loop without session management.
                    # Best practice: Return result, batch save later.
                    # Or use a scoped session. For now, we'll return, and assume volatile until next save?
                    # Actually, let's just return the keys and save batch or individual if connection allows.
                    # Given DB is sync, we can't easily write inside async worker without blocking.
                    # Solution: Return metadata updates, apply in main thread.
                except Exception as e:
                    print(f"Error summarizing {v.filename}: {e}")
                    summary = f"Error summarizing video: {v.filename}"
            else:
                 print(f"Using Cached Summary for {v.filename}", flush=True)

            return (i, summary, v)

    # Launch Swarm
    tasks = [summarize_worker(i, v) for i, v in enumerate(videos)]
    yield f"Launching {len(tasks)} parallel summarization agents..."
    
    results = await asyncio.gather(*tasks)
    
    # Process Results & Batch Persist
    for (i, summary, v) in results:
        # Update Object (InMemory)
        meta = v.metadata_json or {}
        if summary and not meta.get("summary"):
             meta["summary"] = summary
             v.metadata_json = meta
             # Mark dirtiness? We need to commit.
             # Since 'v' is attached to 'db' session, we can commit once at the end?
             # Yes, assuming session is valid.
        
        summaries[i] = f"<VIDEO_SUMMARY filename='{v.filename}'>\n{summary}\n</VIDEO_SUMMARY>"
    
    try:
        db.commit() # Batch Commit all cached summaries
        print("Batch committed new video summaries.", flush=True)
    except Exception as e:
        print(f"Failed to batch commit summaries: {e}")

    full_summary_context = "\n".join(summaries)
    
    print("--- Phase 2: Master Plan Reduce ---", flush=True)
    yield "Phase 2: Architecting Master Course Plan (Reduce)..."
    master_plan = await generate_master_plan(full_summary_context, rules, detected_context)
    print(f"Master Plan Generated: {len(master_plan.get('modules', []))} Modules", flush=True)

    # Sanitize Modules (Defensive Coding)
    valid_modules = []
    for m in master_plan.get("modules", []):
        if isinstance(m, dict):
            valid_modules.append(m)
        else:
            print(f"  ⚠️ Dropping malformed module entry from Master Plan: {m}", flush=True)
    master_plan["modules"] = valid_modules

    # PERSISTENCE: Save Master Plan IMMEDIATELY
    curr_id = None
    try:
        new_plan = k_models.TrainingCurriculum(
            title=master_plan.get("course_title", "Untitled Course"),
            structured_json=master_plan
        )
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        curr_id = new_plan.id
        print(f"Created Curriculum ID {curr_id} (Master Plan Saved)", flush=True)
    except Exception as e:
        print(f"Failed to create curriculum record: {e}")
    
    print("--- Phase 3: Detail Expansion (Parallel Swarm) ---", flush=True)
    yield f"Phase 3: Expanding {len(master_plan.get('modules', []))} Modules (Parallel Swarm)..."
    
    sem_modules = asyncio.Semaphore(10) # 10 Modules at once

    async def expand_module_worker(i, module):
        async with sem_modules:
            print(f"Expanding Module: {module.get('title')}...", flush=True)
            
            # Determine context for this module
            source_filenames = module.get("recommended_source_videos", [])
            module_videos = [v for v in videos if v.filename in source_filenames]
            
            module_context = ""
            if not module_videos:
                 print("No specific source video cited for module, using GLOBAL SUMMARIES context for detail (fallback).", flush=True)
                 module_context = full_summary_context
            else:
                 # Standard Context (Chunking Logic handles overflow inside the function)
                 module_context = build_full_context(module_videos)
                 print(f"  Using Specific Context from {len(module_videos)} videos: {[v.filename for v in module_videos]}", flush=True)
                 
            # Detect empty context
            if not module_context or not module_context.strip():
                 print("Specific context was empty. Falling back to GLOBAL SUMMARIES context.", flush=True)
                 module_context = full_summary_context
                 
            try:
                detailed_module = await generate_detailed_module_validated(module, module_context)
                return (i, detailed_module)
            except Exception as e:
                print(f"FAILED Expanding Module {i+1}: {e}")
                module["error"] = str(e)
                return (i, module)

    # Pre-fill with skeletons so we don't save "None" holes during incremental updates
    final_modules = list(master_plan.get("modules", []))
    
    yield f"Launching {len(final_modules)} parallel detail agents..."
    module_tasks = [expand_module_worker(i, m) for i, m in enumerate(master_plan.get("modules", []))]
    
    # Execute Swarm with INCREMENTAL PERSISTENCE (Save as you go)
    print(f"  🚀 Swarm Active: {len(module_tasks)} agents. Saving incrementally...", flush=True)
    
    for future in asyncio.as_completed(module_tasks):
        try:
            i, detailed_module = await future
            final_modules[i] = detailed_module
            
            # Immediate Save
            if curr_id:
                 master_plan["modules"] = final_modules
                 save_curriculum_checkpoint(db, curr_id, master_plan)
                 print(f"  💾 Checkpoint Saved: Module {i+1} completed.", flush=True)
                 
        except Exception as e:
            print(f"  ❌ Critical Error in Module Worker: {e}", flush=True)

    # Note: Phase 4 (Enrichment) is already parallelized.
    
    master_plan["modules"] = final_modules


    
    # Phase 4: Enrich
    async for status in enrich_curriculum_generator(master_plan, db, detected_context=detected_context, curriculum_id=curr_id):
        yield status
        if isinstance(status, dict):
             master_plan = status

    master_plan["id"] = curr_id
    yield master_plan

async def repair_curriculum(db: Session, curriculum_id: int, target_phases: list = None):
    """
    Surgical Repair: Scans an existing curriculum for missing data and re-runs specific agents.
    Yields status updates.
    modes: ["phase_3", "phase_4"]
    """
    if target_phases is None:
        target_phases = ["phase_3", "phase_4"]
        
    yield f" Inspecting Curriculum ID {curriculum_id} for gaps in {target_phases}..."
    
    plan_record = db.query(k_models.TrainingCurriculum).get(curriculum_id)
    if not plan_record:
        yield {"error": "Curriculum not found."}
        return

    master_plan = plan_record.structured_json
    modules = master_plan.get("modules", [])
    if not modules:
        yield "Error: No modules found in Master Plan. Cannot repair empty plan."
        return

    # --- PRE-FETCH RESOURCES ---
    # Fetch all videos once for both Phase 3 (Repair) and Phase 4 (Context)
    all_videos = db.query(k_models.VideoCorpus).all()
    # Map by filename for easy lookup in Phase 3
    video_map = {v.filename: v for v in all_videos}

    # --- REPAIR PHASE 3: Missing Lessons (Expansion) ---
    if "phase_3" in target_phases:
        incomplete_indices = []
        
        for i, mod in enumerate(modules):
            # Check if module has lessons
            if not mod.get("lessons") or len(mod.get("lessons")) == 0:
                print(f"  ⚠️ Module {i+1} '{mod.get('title')}' is missing lessons. Marking for repair.", flush=True)
                incomplete_indices.append(i)
            elif mod.get("error"):
                 print(f"  ⚠️ Module {i+1} has error state. Marking for retry.", flush=True)
                 incomplete_indices.append(i)

        if incomplete_indices:
            yield f"Found {len(incomplete_indices)} incomplete modules. Launching repair swarm..."
            
            # Needed Filenames
            needed_filenames = set()
            for i in incomplete_indices:
                needed_filenames.update(modules[i].get("recommended_source_videos", []))
            
            # Worker Definition (Scoped)
            sem_modules = asyncio.Semaphore(10)
            async def repair_worker(i, module):
                 async with sem_modules:
                    print(f"Reparing Module {i+1}...", flush=True)
                    source_filenames = module.get("recommended_source_videos", [])
                    
                    # Robust Python Matching
                    module_videos = []
                    missing_files = []
                    
                    for fname in source_filenames:
                        if fname in video_map:
                            module_videos.append(video_map[fname])
                        else:
                            # Try simple normalization fallback (trim)
                            found_fuzzy = False
                            for v in all_videos:
                                if v.filename.strip() == fname.strip():
                                    module_videos.append(v)
                                    found_fuzzy = True
                                    break
                            if not found_fuzzy:
                                missing_files.append(fname)

                    module_context = ""
                    if module_videos:
                         module_context = build_full_context(module_videos)
                    else:
                         missing_files = source_filenames
                    
                    if not module_context:
                         err_msg = f"Cannot Repair: Missing Context. Source videos {missing_files} not found in library."
                         print(f"  ❌ {err_msg}", flush=True)
                         module["error"] = err_msg
                         return (i, module)
                    
                    try:
                        detailed = await generate_detailed_module_validated(module, module_context)
                        
                        # Double Check: If detailed returns 0 lessons, that's also a failure for repair mode
                        if not detailed.get("lessons") or len(detailed.get("lessons")) == 0:
                             err_msg = "Generation Failed: LLM returned 0 lessons despite valid context."
                             module["error"] = err_msg
                             return (i, module)
                             
                        return (i, detailed)
                    except Exception as e:
                        module["error"] = str(e)
                        return (i, module)

            tasks = [repair_worker(i, modules[i]) for i in incomplete_indices]
            
            print(f"  🚀 Repair Swarm Active: {len(tasks)} agents.", flush=True)
            
            # Wait for ALL to complete (Batch Strategy) - Safer for data integrity
            results = await asyncio.gather(*tasks)
            
            success_count = 0
            for (i, detailed_module) in results:
                if detailed_module.get("error"):
                     yield f"  ❌ Module {i+1} Failed: {detailed_module.get('error')}"
                     modules[i] = detailed_module
                else:
                    modules[i] = detailed_module
                    lesson_count = len(detailed_module.get('lessons', []))
                    yield f"  ✅ Repaired Module {i+1} ({lesson_count} lessons)"
                    success_count += 1
            
            # ATOMIC SAVE at the end
            if success_count > 0:
                print(f"  💾 Persisting {success_count} repaired modules to DB...", flush=True)
                master_plan["modules"] = modules
                save_curriculum_checkpoint(db, curriculum_id, master_plan)
                yield "  💾 Database Updated."
            
            yield "Phase 3 Repair Process Finished."
        else:
            yield "Phase 3 (Expansion) looks healthy. No empty modules found."
    else:
        yield "Skipping Phase 3 Check."

    # --- REPAIR PHASE 4: Enrichment ---
    if "phase_4" in target_phases:
        # Pre-flight Check
        total_lessons = sum(len(m.get("lessons", [])) for m in master_plan.get("modules", []))
        if total_lessons == 0:
            yield "❌ Cannot run Enrichment (Phase 4): No lessons found in this curriculum. Please run Phase 3 first."
            yield {"type": "error", "msg": "Phase 4 Aborted: No lessons to enrich."}
            return

        yield "Verifying Enrichment (Phase 4)..."
        
        # Quick re-detect or default for context
        detected_context = await detect_domain_context(all_videos) 
        
        async for status in enrich_curriculum_generator(master_plan, db, detected_context=detected_context, curriculum_id=curriculum_id):
             # Pass through status messages
             if isinstance(status, str):
                 yield status
    else:
        yield "Skipping Phase 4 Check."
    
    yield {"type": "result", "payload": master_plan}
    yield "Repair Complete."

async def detect_domain_context(videos: list) -> dict:
    """
    Analyzes a sample of the corpus (titles + first 20k chars) to determine the Subject Domain.
    """
    # Sample Titles
    titles = [v.filename for v in videos[:10]]
    # Sample Context (first video)
    sample_context = build_full_context(videos[:1])[:5000]
    
    prompt = f"""
    Analyze these video filenames and this snippet of transcript content to identify the Training Context.
    
    Filenames: {titles}
    
    Transcript Sample:
    {sample_context}
    
    Identify:
    1. "instructor_persona": Who is teaching? (e.g. "Senior Utility Trainer", "BJJ Black Belt", "Python Expert")
    2. "student_persona": Who is learning? (e.g. "Work Order Clerk", "White Belt", "Junior Dev")
    3. "target_domain": What is the subject? (e.g. "Utility Pole Inspection", "Brazilian Jiu-Jitsu", "Backend Engineering")
    4. "quiz_focus_areas": What are 3 key things to test? (e.g. ["Safety", "Defect Coding", "Priorities"] or ["Submissions", "Sweeps", "Defense"])
    
    Output JSON:
    {{
        "instructor_persona": "...",
        "student_persona": "...",
        "target_domain": "...",
        "quiz_focus_areas": ["...", "...", "..."]
    }}
    """
    
    # Default Fallback
    fallback = {
        "instructor_persona": "Senior Technical Instructor",
        "student_persona": "New Trainee",
        "target_domain": "General Technical Operations",
        "quiz_focus_areas": ["Key Concepts", "Procedure Steps", "Safety"]
    }
    
    try:
         print("Detecting Domain Context...", flush=True)
         context = await llm.generate_structure(
             system_prompt="You are a Context Analyzer.", 
             user_content=prompt,
             model="x-ai/grok-4.1-fast"
         )
         print(f"Detected Context: {context}", flush=True)
         return context
    except Exception as e:
         print(f"Context Detection Failed: {e}", flush=True)
         return fallback


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

async def generate_master_plan(summary_context: str, rules: str, detected_context: dict = None) -> dict:
    """
    Phase 2: Master Skeleton
    """
    prompt = f"""
    You are the Curriculum Architect.
    {rules}
    
    Review these Video Summaries and design a Complete Course Structure.
    Target Audience: New Employees.
    
    Requirements:
    1. **Pedagogical Structure (Hybrid Strategy)**:
       - **GOAL**: Create the BEST possible training path for mastery.
       - **Strategy**: **Synthesize & Condense**. Do NOT just map 1 video to 1 module.
       - **Aggregation**: Group multiple related videos into single, cohesive Modules (e.g., "Safety Intro" + "Safety Advanced" -> "Module 1: Complete Safety").
       - **Efficiency**: Eliminate redundancy. Create the *fastest* path to competence for a New Trainee.
    
    2. **Professional Naming (STRICT)**:
       - **CRITICAL**: Do NOT use filenames (e.g. "preview_day1.mp4") as Titles.
       - **INVENT** new, professional titles based on the *SKILL* being taught (e.g. "Unit 1: Fundamentals of GIS").
       - Titles must be "Human-Readable" and "Corporate Training Standard".
    
    3. **Module Description**:
       - Generate a high-quality, 2-sentence overview for the UI.

    4. **Source Mapping**:
       - You must strictly set "recommended_source_videos": ["exact_filename.mp4"].
    
    Output JSON format:
    {{
      "course_title": "Mastering [Topic]",
      "course_description": "...",
      "modules": [
        {{
           "title": "Module 1: [Professional Title]", 
           "description": "A high-level overview...",
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
    1. If context > 1.5M characters, SKIP straight to Chunking (Split & Recombine).
    2. Else, Try Standard Full-Context Generation.
    3. If Standard fails, Switch to Chunking.
    """
    
    # STRATEGY FORCE: Always use Chunking (Map-Reduce) for maximum fidelity and reliability.
    # User feedback indicates Standard Generation (Single Shot) is prone to JSON errors with this model/prompt complexity.
    # Chunking has proven 100% reliable.
    print(f"  ⚡ Enforcing High-Fidelity Chunking Strategy for '{module_skeleton.get('title')}'...", flush=True)
    return await generate_module_in_chunks(module_skeleton, context_str)

async def generate_module_in_chunks(module_skeleton: dict, context_str: str) -> dict:
    """
    Fidelity Fix: Splits massive context into chunks, generates lessons for each, and merges.
    """
    # 1. Split Context into Chunks
    # Reduced to 50k to ensure LLM attention
    # 1. Split Context into Chunks
    # Increased to 150k to reduce fragmentation (User Feedback: "Too many lessons")
    CHUNK_SIZE = 150000 
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
        
    print(f"  🔄 Splitting into {len(chunks)} chunks (150k chars) for High Fidelity...", flush=True)
    
    all_lessons = []
    
    # Parallel Execution
    # Global Limit = (10 Concurrent Modules) * (5 Chunks/Module) = 50 Total Agents.
    sem = asyncio.Semaphore(5) 
    
    async def process_chunk(i, chunk):
        async with sem:
            for attempt in range(3):
                try:
                    if attempt > 0:
                        print(f"  ⚠️ Retry {attempt+1}/3 for Chunk {i+1}...", flush=True)
                    else:
                        print(f"  📝 Processing Chunk {i+1}/{len(chunks)}...", flush=True)
                        
                    chunk_prompt = f"""
                    You are the Content Developer.
                    We are detailing a SECTION of the Module: "{module_skeleton.get('title')}".
                    
                    PARTIAL Context Data (Part {i+1}/{len(chunks)}):
                    {chunk}
                    
                    Task:
                    1. Extract and create detailed Lessons FOUND ONLY IN THIS PARTIAL CONTEXT.
                    2. Do not hallucinate lessons from other parts.
                    3. CRITICAL: Include "source_clips" as OBJECTS with "video_filename", "start_time", and "end_time".
                    4. You MUST include a "voiceover_script" for every lesson.
                    5. You MUST use the key "title" for the lesson name (do NOT use "lesson_title").
                    
                    Output JSON:
                    {{
                      "lessons": [ ... ]
                    }}
                    """
                    
                    result = await llm.generate_structure(
                        system_prompt="Extract lessons from this context chunk.",
                        user_content=chunk_prompt,
                        model="x-ai/grok-4.1-fast"
                    )
                    
                    lessons = result.get("lessons", [])
                    return lessons
                    
                except Exception as e:
                    print(f"  ❌ Chunk {i+1} Failed (Attempt {attempt+1}): {e}", flush=True)
                    if attempt == 2:
                        print(f"  🚨 Chunk {i+1} PERMANENTLY FAILED after 3 attempts.", flush=True)
                        return []
                    await asyncio.sleep(1 * (attempt + 1)) # Backoff
            return []

    tasks = [process_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)
    
    # Flatten results
    for lesson_list in results:
        all_lessons.extend(lesson_list)

    # Sanitize lessons (Defensive Coding against malformed LLM outputs)
    sanitized_lessons = []
    for l in all_lessons:
        if isinstance(l, dict):
            sanitized_lessons.append(l)
        elif isinstance(l, str):
            # Fallback for string outputs (rare but possible)
            sanitized_lessons.append({
                "title": l, 
                "learning_objective": "Recovered from raw text",
                "voiceover_script": "",
                "source_clips": []
            })
    all_lessons = sanitized_lessons
        
    # --- CONSOLIDATION PHASE ---
    if len(all_lessons) > 20:
        print(f"  ⚠️ Generated {len(all_lessons)} micro-lessons. Triggering AI Consolidation...", flush=True)
        try:
             # Just map titles/objectives for the prompt to save tokens
             summary_list = [{"id": idx, "title": l.get("title"), "objective": l.get("learning_objective", "")} for idx, l in enumerate(all_lessons)]
             
             consolidation_prompt = f"""
             You are a Senior Curriculum Architect.
             We have generated {len(all_lessons)} fragmented micro-lessons for "{module_skeleton.get('title')}".
             
             Task:
             1. Consolidate these micro-lessons into a cohesive, high-impact course of **10-15 Lessons**.
             2. Group related micro-lessons together.
             
             Input Micro-Lessons:
             {json.dumps(summary_list)}
             
             Output JSON Structure:
             {{
                 "consolidated_lessons": [
                     {{
                         "title": "New Lesson Title",
                         "learning_objective": "New Objective",
                         "source_lesson_ids": [1, 2, 5]  // List of IDs from input list to merge
                     }}
                 ]
             }}
             """
             
             structure = await llm.generate_structure(
                 system_prompt="Consolidate lessons into a perfect flow.",
                 user_content=consolidation_prompt,
                 model="x-ai/grok-4.1-fast"
             )
             
             final_lessons = []
             for item in structure.get("consolidated_lessons", []):
                 merged_clips = []
                 merged_script = ""
                 
                 for source_id in item.get("source_lesson_ids", []):
                     if 0 <= source_id < len(all_lessons):
                         source = all_lessons[source_id]
                         merged_clips.extend(source.get("source_clips", []))
                         merged_script += "\n\n" + source.get("voiceover_script", "")
                 
                 # Deduplicate clips? Maybe simplistic for now.
                 final_lessons.append({
                     "title": item.get("title"),
                     "learning_objective": item.get("learning_objective"),
                     "voiceover_script": merged_script.strip(),
                     "source_clips": merged_clips # Keep all clips
                 })
                 
             print(f"  ✨ Consolidated into {len(final_lessons)} master lessons.", flush=True)
             all_lessons = final_lessons
             
        except Exception as e:
            print(f"  ❌ Consolidation Failed: {e}. Falling back to raw list.", flush=True)
            
    # Merge
    print(f"  ✅ Recombined {len(all_lessons)} lessons from {len(chunks)} chunks.", flush=True)
    return {
        "title": module_skeleton.get("title"),
        "lessons": all_lessons, # Already dicts
        "recommended_source_videos": module_skeleton.get("recommended_source_videos", [])
    }

async def enrich_lesson_worker(lesson, instructor, student, domain, quiz_topics, semaphore):
    """
    Worker to enrich a single lesson. Uses semaphore to limit concurrency.
    """
    async with semaphore:
        script = lesson.get("voiceover_script", "")
        if not script:
            return lesson

        title = lesson.get("title", "Lesson")
        try:
            # Smart Context
            context_prompt = f"""
            Analyze this Training Script and generate "Smart Assist" metadata.
            
            Script: "{script}"
            
            Identify:
            1. "compliance_rules": Any strict DOs/DON'Ts implied.
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
                system_prompt=f"You are a Compliance & Support AI for {domain}.",
                user_content=context_prompt,
                model="x-ai/grok-4.1-fast"
            )
            lesson["smart_context"] = smart_context

            # Quiz Generation
            quiz_prompt = f"""
            You are a {instructor}. 
            Your students are "{student}" learning about **{domain}**.
            
            The Lesson Script below teaches specific concepts.
            Verify they understand the critical points related to: {quiz_topics}.
            
            Script: "{script}"
            
            Task:
            Generate a "Job-Critical" multiple-choice quiz.
            
            Output JSON:
            {{
              "questions": [
                {{
                  "question": "...",
                  "options": ["A", "B", "C"],
                  "correct_answer": "A",
                  "explanation": "..."
                }}
              ]
            }}
            """
            
            quiz_data = await llm.generate_structure(
                system_prompt="You are an Instructional Designer.",
                user_content=quiz_prompt,
                model="x-ai/grok-4.1-fast"
            )
            lesson["quiz"] = quiz_data
            
        except Exception as e:
            print(f"Failed to enrich lesson '{title}': {e}", flush=True)
            lesson["smart_context"] = {} # Fallback
            lesson["quiz"] = {} # Fallback
            
        return lesson

async def enrich_curriculum_generator(curriculum_data: dict, db: Session = None, detected_context: dict = None, curriculum_id: int = None):
    """
    Phase 4: Knowledge Enrichment (Parallelized + Persistent)
    """
    print("--- Phase 4: Knowledge Enrichment (Smart Assist) ---", flush=True)
    yield "Phase 4: Starting Knowledge Enrichment (Parallelized)..."
    
    # Defaults
    instructor = "Senior Technical Instructor"
    student = "New Trainee"
    domain = "General Operations"
    quiz_topics = "Key concepts, safety, and procedures"
    
    if detected_context:
        instructor = detected_context.get("instructor_persona", instructor)
        student = detected_context.get("student_persona", student)
        domain = detected_context.get("target_domain", domain)
        topics = detected_context.get("quiz_focus_areas", [])
        if topics:
            quiz_topics = ", ".join(topics)

    modules = curriculum_data.get("modules", [])
    total_lessons = sum(len(m.get("lessons", [])) for m in modules)
    yield f"Smart Assist: Analyzing {total_lessons} Lessons (Parallel Mode)..."
    
    # Flatten all lessons for parallel processing
    work_items = []
    for m_idx, module in enumerate(modules):
        for l_idx, lesson in enumerate(module.get("lessons", [])):
            work_items.append((m_idx, l_idx, lesson))
            
    # Semaphore to limit concurrency (Protect API limits)
    semaphore = asyncio.Semaphore(10)
    
    tasks = []
    for (m_idx, l_idx, lesson) in work_items:
        task = enrich_lesson_worker(lesson, instructor, student, domain, quiz_topics, semaphore)
        tasks.append(task)
        
    print(f"Launching {len(tasks)} parallel enrichment tasks...", flush=True)
    yield f"Launching {len(tasks)} parallel AI agents..."
    
    CHUNK_SIZE = 20
    
    # Split into chunks for incremental saving
    for i in range(0, len(tasks), CHUNK_SIZE):
        chunk_tasks = tasks[i:i+CHUNK_SIZE]
        chunk_indices = work_items[i:i+CHUNK_SIZE]
        
        yield f"Enriching Batch {i//CHUNK_SIZE + 1} (Lessons {i+1}-{min(i+CHUNK_SIZE, len(tasks))})..."
        
        results = await asyncio.gather(*chunk_tasks)
        
        # Update Main Structure
        for j, enriched_lesson in enumerate(results):
            m_idx, l_idx, _ = chunk_indices[j]
            curriculum_data["modules"][m_idx]["lessons"][l_idx] = enriched_lesson
            
        # PERSISTENCE: Save after every batch
        if curriculum_id and db:
             save_curriculum_checkpoint(db, curriculum_id, curriculum_data)
             
    yield "Enrichment Complete. Finalizing Course Plan..."
    yield curriculum_data
