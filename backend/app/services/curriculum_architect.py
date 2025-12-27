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
    master_plan = await generate_master_plan(full_summary_context, rules, detected_context)
    print(f"Master Plan Generated: {len(master_plan.get('modules', []))} Modules", flush=True)

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

        # PERSISTENCE: Update DB after EACH module
        if curr_id:
             # Merge current progress with remaining skeletons
             temp_plan = master_plan.copy()
             merged_modules = final_modules + master_plan.get("modules", [])[len(final_modules):]
             temp_plan["modules"] = merged_modules
             save_curriculum_checkpoint(db, curr_id, temp_plan)

        # PERSISTENCE: Update DB after EACH module
        if curr_id:
             # Merge current progress with remaining skeletons
             temp_plan = master_plan.copy()
             merged_modules = final_modules + master_plan.get("modules", [])[len(final_modules):]
             temp_plan["modules"] = merged_modules
             save_curriculum_checkpoint(db, curr_id, temp_plan)

    master_plan["modules"] = final_modules
    
    master_plan["modules"] = final_modules
    
    # Phase 4: Enrich
    async for status in enrich_curriculum_generator(master_plan, db, detected_context=detected_context, curriculum_id=curr_id):
        yield status
        if isinstance(status, dict):
             master_plan = status

    yield master_plan

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
    2. You MUST define "source_clips" as OBJECTS (not strings) with "start_time" and "end_time" matching the Context.
    3. Example: "source_clips": [{{ "start_time": "10.5s", "end_time": "20.0s", "reason": "Demonstrates X" }}]
    4. Verify timestamps exist.
    
    Output JSON (Module Object only):
    {{
        "title": "{module_skeleton.get('title')}",
        "lessons": [ ... (full lesson structure with voiceover_script and source_clips) ... ],
        "recommended_source_videos": {json.dumps(module_skeleton.get('recommended_source_videos', []))}
    }}
    CRITICAL: Return the raw Module object. Do NOT wrap it in a "module" or "lesson" key.
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
    # Reduced to 50k to ensure LLM attention
    CHUNK_SIZE = 50000 
    OVERLAP = 2000
    
    chunks = []
    start = 0
    while start < len(context_str):
        end = min(start + CHUNK_SIZE, len(context_str))
        chunk = context_str[start:end]
        chunks.append(chunk)
        if end == len(context_str):
            break
        start = end - OVERLAP
        
    print(f"  🔄 Splitting into {len(chunks)} chunks (50k chars) for High Fidelity...", flush=True)
    
    all_lessons = []
    
    # Parallel Execution
    sem = asyncio.Semaphore(10) # Process 10 chunks concurrentl
    
    async def process_chunk(i, chunk):
        async with sem:
            print(f"  📝 Processing Chunk {i+1}/{len(chunks)}...", flush=True)
            chunk_prompt = f"""
            You are the Content Developer.
            We are detailing a SECTION of the Module: "{module_skeleton.get('title')}".
            
            PARTIAL Context Data (Part {i+1}/{len(chunks)}):
            {chunk}
            
            Task:
            1. Extract and create detailed Lessons FOUND ONLY IN THIS PARTIAL CONTEXT.
            2. Do not hallucinate lessons from other parts.
            3. Include "source_clips" as OBJECTS: [{{ "start_time": "...", "end_time": "..." }}]. DO NOT use plain strings.
            4. You MUST include a "voiceover_script" for every lesson.
            5. You MUST use the key "title" for the lesson name (do NOT use "lesson_title").
            
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
                count = len(partial_module.lessons)
                if count > 0:
                    print(f"  ✅ Chunk {i+1} yielded {count} lessons.", flush=True)
                else:
                     print(f"  ⚠️ Chunk {i+1} yielded 0 lessons.", flush=True)
                return partial_module.lessons
            except Exception as e:
                print(f"  ❌ Failed to process chunk {i+1}: {e}", flush=True)
                return []

    tasks = [process_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)
    
    # Flatten results
    for lesson_list in results:
        all_lessons.extend(lesson_list)
            
    # Merge
    print(f"  ✅ Recombined {len(all_lessons)} lessons from {len(chunks)} chunks.", flush=True)
    return {
        "title": module_skeleton.get("title"),
        "lessons": [l.model_dump() for l in all_lessons],
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
