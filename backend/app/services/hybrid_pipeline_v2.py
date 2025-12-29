
import pypdf
import json
import logging
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from ..models import knowledge as k_models
from . import llm

logger = logging.getLogger(__name__)

# --- Models ---
class BlueprintLesson(BaseModel):
    title: str
    description: Optional[str] = "No description provided."

class BlueprintModule(BaseModel):
    title: str
    description: str
    lessons: List[BlueprintLesson]

class BlueprintCourse(BaseModel):
    title: str
    description: str
    modules: List[BlueprintModule]

class HybridQuiz(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    explanation: str

class HybridLessonContent(BaseModel):
    voiceover_script: str
    learning_objective: str
    key_takeaways: List[str]
    estimated_reading_time_minutes: float
    is_simulation: bool = False
    simulation_scenario: Optional[str] = None
    quiz: HybridQuiz
    visual_aid_description: Optional[str] = None

# --- Prompts ---
BLUEPRINT_PROMPT = """
You are a Curriculum Architect.
Your task is to Analyze the Source Text and design a Course BLUEPRINT (Structure Only).

CRITICAL REQUIREMENT:
You MUST cover the ENTIRETY of the provided Source Text.
- Do NOT summarize or condense significantly.
- Every major section of the Source Text should have a corresponding Module.
- Every key concept should have a Lesson.
- Structure it for maximum training efficacy, but do NOT leave any content out.

Output VALID JSON:
{
  "title": "Course Title",
  "description": "Course Overview",
  "modules": [
    {
      "title": "Module 1",
      "description": "...",
      "lessons": [{"title": "L1", "description": "High-level summary of what this lesson covers..."}]
    }
  ]
}
"""

CONTENT_PROMPT = """
You are a Technical Writer.
Your task is to write the FULL CONTENT for this specific Lesson based on the provided Source Text.

CRITICAL REQUIREMENT:
- Use ALL relevant training material from the Source Text for this lesson.
- Do NOT omit technical details, warnings, or steps.
- The Voiceover Script must be comprehensive and instructional.
- Ensure strict technical accuracy based *only* on the Source Text.

You MUST output a VALID JSON object adhering to this EXACT structure:
{
  "voiceover_script": "Full narration script...",
  "learning_objective": "The main goal of this lesson...",
  "key_takeaways": ["Point 1", "Point 2", "Point 3"],
  "estimated_reading_time_minutes": 5.0,
  "is_simulation": false,
  "simulation_scenario": null,
  "quiz": {
    "question": "Quiz question?",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "Option A",
    "explanation": "Why A is correct..."
  },
  "visual_aid_description": "Description of visual aids..."
}
"""

# --- Service ---
def extract_text_from_pdf(file_path: str) -> str:
    try:
        reader = pypdf.PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error reading PDF {file_path}: {e}")
        return ""

def clean_text(text: str) -> str:
    """
    Sanitizes extracted text to remove problematic characters for LLM/JSON safety.
    """
    if not text:
        return ""
    # Remove null bytes and replacement chars
    text = text.replace('\x00', '').replace('\ufffd', '')
    # Remove other control chars (keep newlines/tabs)
    return "".join(ch for ch in text if ch == '\n' or ch == '\r' or ch == '\t' or ord(ch) >= 32)
    
# --- New Models for Global Matching ---
class VideoMatch(BaseModel):
    lesson_title: str = Field(description="Exact title of the lesson to match")
    video_filename: str = Field(description="The filename of the matched video")
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    reason: str = Field(description="Why this clip is a perfect match")

class GlobalVideoMatchResponse(BaseModel):
    matches: List[VideoMatch]

# --- Global Match Prompt ---
SYSTEM_GLOBAL_MATCH_PROMPT = """
You are a Video Content Curator.
Your task is to review the ENTIRE Course Blueprint and the ENTIRE Video Library to find perfect video clips for each Lesson.

INPUT 1: Course Blueprint (Modules & Lessons)
INPUT 2: Global Video Library (Transcripts & Timestamps)

CRITICAL INSTRUCTION:
1. Scan every Lesson in the Course.
2. Search the Video Library for segments that explain the lesson's concept.
3. Return a list of 'matches'.

MATCHING CRITERIA:
- High Semantic Relevance: The video must actually teach the concept.
- precise Timestamps: If timestamps are available in the text, use them. If not, default to 0.0 to 60.0.

OUTPUT FORMAT:
Return a JSON object with a "matches" key containing a list of objects.
Each object must have:
- "lesson_title": Exact string match to the Lesson inputs.
- "video_filename": Exact filename from the Video Library input.
- "start_time": float (seconds)
- "end_time": float (seconds)
- "reason": Brief explanation.
"""

async def stage_1_generate_course(db: Session, doc_id: int) -> k_models.HybridCurriculum:
    """
    Stage 1: Generate Course Structure (Blueprint) -> Fill Content.
    """
    # Idempotency Check: if course already exists for this doc, return it.
    # We assume 1-to-1 mapping for simplicity in this flow, or finding by title.
    # Since we don't have a direct link in HybridCurriculum to DocID easily queryable (original_curriculum_id is for TrainingCurriculum),
    # we'll skip this strict check or just rely on the caller validation. 
    # BUT, the user asked for "checks... for data we don't yet have".
    # Let's check by title match or if the doc was already processed? 
    # For now, we will assume re-running Stage 1 implies intent to regenerate unless we see a finished record.
    pass 
    
    # 1. Get Doc
    doc = db.query(k_models.KnowledgeDocument).get(doc_id)
    if not doc or not doc.file_path:
        raise ValueError(f"Document {doc_id} not found")
        
    print(f"Checking for cached text in Document {doc.id}...")
    full_text = doc.extracted_text
    
    if not full_text:
        print(f"No cache found. Extracting text from {doc.filename}...")
        raw_text = extract_text_from_pdf(doc.file_path)
        if not raw_text:
            raise ValueError("Failed to extract text")
        
        # Clean
        print("Cleaning extracted text...")
        full_text = clean_text(raw_text)
        
        # Cache it
        print("Caching extracted text to DB...")
        doc.extracted_text = full_text
        db.add(doc)
        db.commit()
    else:
        print(f"Using cached text ({len(full_text)} chars).")
        # Ensure cached text is also cleaned if it wasn't before
        if '\ufffd' in full_text:
            print("Detected artifacts in cache. Cleaning...")
            full_text = clean_text(full_text)
            doc.extracted_text = full_text
            db.commit()
        
    print(f"Source Text Length: {len(full_text)} chars.")
    
    import asyncio # Ensure available for resume path
    
    # Check if we already have a course with this title (Idempotency Proxy)
    # This is a bit weak but prevents obvious dupes if the user blindly re-runs.
    existing_course = db.query(k_models.HybridCurriculum).filter(k_models.HybridCurriculum.title.ilike(f"%{doc.filename}%")).first()
    
    # MANUAL OVERRIDE for OH Book (Doc 10 -> Course 4)
    if doc_id == 10 and not existing_course:
        existing_course = db.query(k_models.HybridCurriculum).get(4)

    if existing_course:
         print(f" found existing course '{existing_course.title}' (ID: {existing_course.id}). returning it.")
         # If not fully generated, we might want to resume? 
         # The prompt logic below handles "resume" for lessons. 
         # But for Blueprint gen, we assume if record exists, Blueprint is done.
         # So we fall through to the Expansion loop directly.
         blueprint = None 
         new_course = existing_course
         course_id = new_course.id
         print("Resuming Content Generation for existing course...")
    else:
        # 2. Generate Blueprint (Recursive Strategy)
        logger.info("Generating Blueprint Skeleton...")
        
        # 2a. Define Recursive Models locally to avoid global clutter
        class BlueprintModuleSkeleton(BaseModel):
            title: str
            description: Optional[str] = "No description provided."
            start_match: Optional[str] = Field(description="The first unique ~20 character sentence/phrase of this module in the text.")
            end_match: Optional[str] = Field(description="The last unique ~20 character sentence/phrase of this module in the text.")
    
        class BlueprintCourseSkeleton(BaseModel):
            title: Optional[str] = None
            description: Optional[str] = "No description provided."
            modules: List[BlueprintModuleSkeleton]
            
        class ModulePlan(BaseModel):
            lessons: List[BlueprintLesson] = Field(default_factory=list)
    
        SYSTEM_SKELETON_PROMPT = """
        You are a Curriculum Architect.
        Analyze the Source Text and design the High-Level Course Structure.
        
        1. EXTRACT the Course Title and a brief Description.
        2. LIST all Modules (Major Sections/Chapters).
        3. LOCATE the exact start and end text for each module.
        
        CRITICAL OUTPUT FORMAT:
        Return Valid JSON. Use EXACT keys: "title", "description", "start_match", "end_match".
        "start_match": Copy the FIRST sentence or unique phrase of the section EXACTLY.
        "end_match": Copy the LAST sentence or unique phrase of the section EXACTLY.
        
        CRITICAL REQUIREMENT:
        - Cover the ENTIRETY of the source text.
        - Create a Module for every major section.
        - Do NOT generate lessons yet.
        """
        
        SYSTEM_MODULE_PROMPT = """
        You are a Curriculum Architect.
        For the specific Module provided, design the detailed Lesson Plan.
        
        CONTEXT:
        The user has provided ONLY the text relevant to this module.
        
        CRITICAL REQUIREMENT:
        - Create granular lessons covering all key concepts in this matched text.
        - Ensure logical flow.
        """
    
        # 2b. Generate Skeleton
        try:
            skeleton = await llm.generate_structure_validated(
                system_prompt=SYSTEM_SKELETON_PROMPT,
                user_content=f"SOURCE TEXT (Full Context):\n{full_text}\n...", 
                model_class=BlueprintCourseSkeleton,
                model="x-ai/grok-4.1-fast",  
                max_retries=3
            )
            # Failover Title
            course_title = skeleton.title if skeleton.title else f"Course: {doc.filename}"
            course_desc = skeleton.description if skeleton.description else "Generated from PDF source."
            
            print(f"Skeleton Created: '{course_title}' with {len(skeleton.modules)} Modules.")
        except Exception as e:
            print(f"Skeleton Gen Failed: {e}")
            raise e
            
        # 2c. Expand Modules into Full Blueprint (With Slicing)
        print("Expanding Modules into Lessons (Slicing Context)...")
        full_modules = []
        
        async def expand_module(mod_skel: BlueprintModuleSkeleton) -> BlueprintModule:
            # Resolve Context Slice
            module_text = full_text # Default
            if mod_skel.start_match and mod_skel.end_match:
                s_idx = full_text.find(mod_skel.start_match)
                e_idx = full_text.find(mod_skel.end_match)
                
                if s_idx != -1 and e_idx != -1:
                    # Add buffer and slice
                    start_safe = max(0, s_idx)
                    end_safe = min(len(full_text), e_idx + len(mod_skel.end_match) + 100)
                    if end_safe > start_safe:
                        module_text = full_text[start_safe:end_safe]
                        print(f"Module '{mod_skel.title}' sliced to {len(module_text)} chars.")
                else:
                    print(f"Warning: Could not exact-match context for '{mod_skel.title}'. Using full text.")
            
            try:
                plan = await llm.generate_structure_validated(
                    system_prompt=SYSTEM_MODULE_PROMPT,
                    user_content=f"MODULE: {mod_skel.title}\nDESCRIPTION: {mod_skel.description}\nMODULE TEXT:\n{module_text}",
                    model_class=ModulePlan,
                    model="x-ai/grok-4.1-fast",
                    max_retries=3
                )
                
                # Fallback for empty lessons
                if not plan.lessons:
                     plan.lessons = [
                        BlueprintLesson(title=f"{mod_skel.title} Overview", description="Review of the module content.")
                    ]
                    
                return BlueprintModule(
                    title=mod_skel.title,
                    description=mod_skel.description,
                    lessons=plan.lessons
                )
            except Exception as e:
                print(f"Failed to expand module {mod_skel.title}: {e}")
                # Fallback: 1 generic lesson
                return BlueprintModule(
                    title=mod_skel.title,
                    description=mod_skel.description,
                    lessons=[BlueprintLesson(title=f"{mod_skel.title} Overview", description="Overview of this module.")]
                )
                
        # Parallelize Module Expansion
        import asyncio
        expansion_tasks = [expand_module(m) for m in skeleton.modules]
        full_modules = await asyncio.gather(*expansion_tasks)
        
        blueprint = BlueprintCourse(
            title=course_title,
            description=course_desc,
            modules=full_modules
        )
            
        import asyncio
        from sqlalchemy.orm.attributes import flag_modified
        
        # 3. Initialize Course in DB (Pending State)
        # create the initial structure with placeholders
        initial_modules = []
        for mod in blueprint.modules:
            mod_lessons = []
            for lesson in mod.lessons:
                # Create placeholder
                mod_lessons.append({
                    "title": lesson.title,
                    "status": "pending",
                    "voiceover_script": "Generating...",
                    "learning_objective": lesson.description,
                    "source_clips": []
                })
            initial_modules.append({
                "title": mod.title,
                "description": mod.description,
                "lessons": mod_lessons
            })
            
        json_structure = {
            "course_title": blueprint.title,
            "course_description": blueprint.description,
            "modules": initial_modules
        }
        
        total_mods = len(initial_modules)
        total_lessons = sum(len(m["lessons"]) for m in initial_modules)
        
        new_course = k_models.HybridCurriculum(
            title=blueprint.title,
            description=blueprint.description,
            structured_json=json_structure,
            total_modules=total_mods,
            total_lessons=total_lessons
        )
        db.add(new_course)
        db.commit()
        db.refresh(new_course)
        
        course_id = new_course.id
        print(f"Blueprint Saved (ID: {course_id}). Starting Parallel Drafting...")

    # 4. Expansion Loop (Parallel Content Generation with Incremental Save)
    # If we just loaded `new_course` from existing, we need to inspect it.
    
    # Reload structure to be sure
    current_course = db.query(k_models.HybridCurriculum).get(course_id)
    structure = current_course.structured_json
    
    semaphore = asyncio.Semaphore(20)
    db_lock = asyncio.Lock()
        
    async def generate_and_save_lesson(mod_idx: int, lesson_idx: int, lesson_data: dict):
        if lesson_data.get("status") == "complete":
            # Idempotency Skip
            return 
            
        async with semaphore:
            print(f"  ▶ STARTING: {lesson_data['title']}...")
            try:
                # Reverted retries to 2 as per user request
                content = await llm.generate_structure_validated(
                    system_prompt=CONTENT_PROMPT + "\nIMPORTANT: You MUST include ALL fields (voiceover_script, learning_objective, key_takeaways, estimated_reading_time_minutes, quiz, visual_aid_description). Do NOT generate a partial object.",
                    user_content=f"LESSON: {lesson_data['title']}\nCONTEXT: {lesson_data['learning_objective']}\nSOURCE: {full_text}", 
                    model_class=HybridLessonContent,
                    model="x-ai/grok-4.1-fast",
                    max_retries=2
                )
                
                print(f"  ✅ DONE: {lesson_data['title']}")
                # Merge new content into existing data
                updated_data = {
                    **lesson_data,
                    "status": "complete",
                    **content.model_dump(),
                }
                
            except Exception as e:
                print(f"  ❌ FAILED {lesson_data['title']}: {e}")
                updated_data = {
                    **lesson_data,
                    "status": "failed",
                    "error_msg": str(e)
                }

            # INCREMENTAL SAVE
            async with db_lock:
                try:
                    # Refresh
                    c = db.query(k_models.HybridCurriculum).get(course_id)
                    s = c.structured_json
                    s["modules"][mod_idx]["lessons"][lesson_idx] = updated_data
                    c.structured_json = s
                    flag_modified(c, "structured_json")
                    db.commit()
                except Exception as save_err:
                    print(f"  ⚠️ DB SAVE ERROR for {lesson_data['title']}: {save_err}")
                    db.rollback()

    tasks = []
    
    # We iterate the CURRENT dict structure
    for m_i, mod in enumerate(structure["modules"]):
        for l_i, lesson in enumerate(mod["lessons"]):
            tasks.append(generate_and_save_lesson(m_i, l_i, lesson))
    
    import asyncio
    await asyncio.gather(*tasks)
    
    # Refresh final return
    db.refresh(current_course)
    return current_course

async def stage_2_enrich_with_video(db: Session, course_id: int):
    """
    Stage 2: Fuse existing videos with the generated course using GLOBAL CONTEXT.
    Idempotent: Checks if matches already exist.
    """
    course = db.query(k_models.HybridCurriculum).get(course_id)
    if not course:
        raise ValueError("Course not found")
        
    structure = course.structured_json
    
    # 1. Idempotency Check
    # Scan structure to see if we have ANY matches content
    existing_matches = 0
    for m in structure["modules"]:
        for l in m["lessons"]:
            if l.get("source_clips"):
                existing_matches += len(l["source_clips"])
    
    if existing_matches > 0:
        print(f"Skipping Stage 2: {existing_matches} video matches already found.")
        return 

    logger.info("Fetching all videos for Global Context...")
    all_videos = db.query(k_models.VideoCorpus).all()
    if not all_videos:
        print("No videos in corpus. Skipping enrichment.")
        return

    # 2. Build Global Video Context
    video_context = ""
    for v in all_videos:
        video_context += f"\n=== VIDEO FILENAME: {v.filename} (ID: {v.id}) ===\n"
        if v.transcript_json:
            # TODO: If we had timestamps, we would loop them here.
            # json_data = v.transcript_json
            # for seg in json_data.get('segments', []):
            #    video_context += f"[{seg['start']}-{seg['end']}] {seg['text']}\n"
             video_context += "(JSON Transcript available but format unknown, passing raw text fallback)\n"
             video_context += str(v.transcript_text)[:50000] # Limit per video?
        elif v.transcript_text:
            # Fallback
            video_context += "(Timestamps Unavailable - Match semantics only)\n"
            video_context += v.transcript_text[:50000] # Cap per video to fit 2M context if needed
        else:
             video_context += "(No Text Available)\n"
             
    print(f"Global Video Context Built: {len(video_context)} chars.")

    # 3. Build Course Context (Blueprint)
    # We want to give the LLM the list of lessons so it knows what to find.
    course_context_str = f"COURSE: {structure.get('course_title')}\n"
    for m in structure["modules"]:
        course_context_str += f"\nMODULE: {m['title']}\n"
        for l in m["lessons"]:
            course_context_str += f" - LESSON: {l['title']}\n   DESC: {l['learning_objective']}\n"
            
    # 4. Global LLM Call
    print("Executing GLOBAL VIDEO MATCH (This may take a minute)...")
    try:
        # We pass the huge contexts. Grok 2M window handles this.
        response = await llm.generate_structure_validated(
            system_prompt=SYSTEM_GLOBAL_MATCH_PROMPT,
            user_content=f"--- COURSE BLUEPRINT ---\n{course_context_str}\n\n--- VIDEO LIBRARY ---\n{video_context}",
            model_class=GlobalVideoMatchResponse,
            model="x-ai/grok-4.1-fast",
            max_retries=2
        )
        
        # 5. Process & Map Matches
        match_map = {} # lesson_title -> list of clips
        for m in response.matches:
            if m.lesson_title not in match_map:
                match_map[m.lesson_title] = []
            
            match_map[m.lesson_title].append({
                "video_filename": m.video_filename,
                "start_time": m.start_time,
                "end_time": m.end_time,
                "reason": m.reason
            })
            
        matches_applied = 0
        
        # Apply to Structure
        for m in structure["modules"]:
            for l in m["lessons"]:
                t = l["title"]
                # Fuzzy or exact match? Prompt asked for "Exact string match".
                # We try exact first.
                if t in match_map:
                    l["source_clips"] = match_map[t]
                    matches_applied += len(match_map[t])
        
        # Persist
        from sqlalchemy.orm.attributes import flag_modified
        course.structured_json = structure
        flag_modified(course, "structured_json")
        db.commit()
        
        print(f"Global Enrichment Complete. Applied {matches_applied} matches across the course.")
        
    except Exception as e:
        print(f"Global Video Match Failed: {e}")

