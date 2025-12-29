import pypdf
import json
import logging
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from ..models import knowledge as k_models
from ..schemas import curriculum as c_schemas
from . import llm

logger = logging.getLogger(__name__)

# --- Pydantic Models for LLM Generation ---

class HybridQuiz(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    explanation: str

class HybridLesson(BaseModel):
    title: str
    voiceover_script: str
    learning_objective: str
    key_takeaways: List[str]
    estimated_reading_time_minutes: float
    is_simulation: bool = False
    simulation_scenario: Optional[str] = None
    quiz: HybridQuiz
    suggested_video_filename: Optional[str] = None
    suggested_video_reason: Optional[str] = None

class HybridModule(BaseModel):
    title: str
    description: str
    lessons: List[HybridLesson]
    
class HybridCourse(BaseModel):
    course_title: str
    course_description: str
    modules: List[HybridModule]

# --- Prompt Engineering ---

HYBRID_DESIGNER_SYSTEM_PROMPT = """
You are a world-class Instructional Designer and Curriculum Architect.
Your task is to synthesize a complete "High-Fidelity" training course based on valid source documents (PDFs) and available video footage.

You will be provided with:
1. THE SOURCE TEXT: Content from PDF documents (SOPs, Manuals, etc.). This is the GROUND TRUTH.
2. AVAILABLE VIDEOS: A list of available video filenames and valid transcripts.

YOUR GOAL:
Create a structured course that teaches the Source Text effectively.
- Break content into logical Modules and Lessons.
- For each lesson, write a full Voiceover Script for the instructor.
- INTELLIGENTLY MATCH VIDEOS: If a concept in the text matches an available video clip, you MUST cite the video filename in 'suggested_video_filename'.
- CREATE ASSESSMENTS: For every lesson, create a Quiz Question to test understanding.
- ENGAGE THE LEARNER: Use "Key Takeaways" and specific "Simulation Scenarios" where applicable.

OUTPUT FORMAT:
You must output VALID JSON matching the specified structure.
Ensures Strings are properly escaped.
"""

# --- Service Implementation ---

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

async def generate_hybrid_curriculum(
    db: Session,
    document_ids: List[int],
    video_ids: List[int]
) -> k_models.TrainingCurriculum:
    
    # 1. Gather Context
    full_source_text = ""
    for doc_id in document_ids:
        doc = db.query(k_models.KnowledgeDocument).filter(k_models.KnowledgeDocument.id == doc_id).first()
        if doc and doc.file_path:
            full_source_text += f"\n--- SOURCE DOC: {doc.filename} ---\n"
            full_source_text += extract_text_from_pdf(doc.file_path)
            
    video_context = ""
    for vid_id in video_ids:
        vid = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.id == vid_id).first()
        if vid:
            transcript = vid.transcript_text[:1000] + "..." if vid.transcript_text else "No transcript"
            video_context += f"\nVIDEO FILE: {vid.filename}\nTRANSCRIPT SNIPPET: {transcript}\n"

    # 2. Construct Prompt
    # We truncate source text to avoid OOM if it's massive, but aim for high retention
    # 500k chars is approx 125k tokens, well within 2M context windows.
    user_content = f"""
    SOURCE MATERIAL:
    {full_source_text[:500000]} 
    
    AVAILABLE VIDEOS:
    {video_context}
    
    INSTRUCTIONS:
    Generate the full course structure now.
    """
    
    # 3. Call LLM
    logger.info("Sending Hybrid Generation Request to LLM...")
    try:
        course_data = await llm.generate_structure_validated(
            system_prompt=HYBRID_DESIGNER_SYSTEM_PROMPT,
            user_content=user_content,
            model_class=HybridCourse,
            max_retries=3
        )
    except Exception as e:
        logger.error(f"LLM Generation Failed: {e}")
        raise e

    # 4. Persistence (Map HybridCourse -> TrainingCurriculum)
    # We need to map our rich HybridLesson to the DB's Lesson structure
    
    db_modules = []
    
    for mod in course_data.modules:
        db_lessons = []
        for less in mod.lessons:
            # Map Quiz and Metadata to smart_context or quiz field
            quiz_data = less.quiz.model_dump()
            
            # Map Source Clips (Smart Match)
            clips = []
            if less.suggested_video_filename:
                # We create a dummy clip with the filename. 
                # Ideally we would find the timestamp, but for now we just link the file.
                clips.append({
                    "video_filename": less.suggested_video_filename,
                    "start_time": 0.0,
                    "end_time": 10.0, # Dummy duration
                    "reason": less.suggested_video_reason or "Suggested by Hybrid Engine"
                })
            
            db_less = {
                "title": less.title,
                "voiceover_script": less.voiceover_script,
                "learning_objective": less.learning_objective,
                "quiz": quiz_data,
                "source_clips": clips,
                "smart_context": {
                    "key_takeaways": less.key_takeaways,
                    "estimated_reading_time": less.estimated_reading_time_minutes,
                    "is_simulation": less.is_simulation,
                    "simulation_scenario": less.simulation_scenario
                }
            }
            db_lessons.append(db_less)
            
        db_modules.append({
            "title": mod.title,
            "description": mod.description,
            "lessons": db_lessons,
            "recommended_source_videos": [] # Could populate this
        })
    
    final_curriculum = {
        "course_title": course_data.course_title,
        "course_description": course_data.course_description,
        "modules": db_modules
    }
    
    # Save to DB
    new_curriculum = k_models.TrainingCurriculum(
        title=course_data.course_title,
        structured_json=final_curriculum
    )
    db.add(new_curriculum)
    db.commit()
    db.refresh(new_curriculum)
    
    return new_curriculum
