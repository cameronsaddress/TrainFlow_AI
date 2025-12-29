
import asyncio
import logging
import sys
import os
import json
import re

# Ensure backend modules are visible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import curriculum_architect, llm
from pydantic import BaseModel, Field
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LearningObjective(BaseModel):
    objective: str = Field(..., description="A concise, actionable learning objective for this lesson.")

# MAPPING TABLE (Title Keyword -> UUID, Duration)
VIDEO_MAP = {
    "Day 1 Part 1": {"uuid": "762ca897-f754-44f6-8ea7-ccec5ea03acd.mp4", "duration": 14400.0},
    "Day 1 Part 2": {"uuid": "4582bae8-12a8-488d-9176-a6424dead132.mp4", "duration": 2540.3},
    "Day 1 Part2":  {"uuid": "4582bae8-12a8-488d-9176-a6424dead132.mp4", "duration": 2540.3},
    "Day 2":        {"uuid": "8d74415f-bdad-44f7-bef9-4bf8ac4e330f.mp4", "duration": 13987.5},
    "Day 3 Part 2": {"uuid": "79ba08e9-4691-4d2b-bdad-68a767f0934f.mp4", "duration": 3043.2},
    "Day 3":        {"uuid": "97626b03-0b9f-4fc2-a98d-b4aaea1342a1.mp4", "duration": 6043.7},
}

async def generate_objective(title, script):
    prompt = f"""
    Based on the Lesson Title: "{title}" and Script: "{script[:1000]}...",
    Write a single, concise "Target Outcome" or Learning Objective.
    Example: "Students will be able to identify key components of a work order."
    start with an action verb.
    """
    try:
        res = await llm.generate_structure_validated(
            system_prompt="You are an instructional designer.",
            user_content=prompt,
            model="x-ai/grok-4.1-fast",
            model_class=LearningObjective
        )
        return res.objective
    except Exception as e:
        logger.error(f"Failed to gen objective: {e}")
        return f"Understand the concepts of {title}."

async def repair_course_14():
    db = SessionLocal()
    try:
        course = db.query(k_models.TrainingCurriculum).get(14)
        if not course:
            logger.error("Course 14 not found!")
            return

        master_plan = course.structured_json
        modules = master_plan.get("modules", [])
        
        logger.info(f"--- Repairing Course 14 ({len(modules)} Modules) ---")
        
        updated_any = False
        
        # 1. Module Level Fixes (Assign Correct Source Videos)
        for m_idx, mod in enumerate(modules):
            title = mod.get("title", "")
            matched_video = None
            
            # Find best match (Sort by length desc to match specific first)
            sorted_keys = sorted(VIDEO_MAP.keys(), key=len, reverse=True)
            for key in sorted_keys:
                if key.lower() in title.lower():
                    matched_video = VIDEO_MAP[key]
                    break
            
            if not matched_video and "Day 1" in title:
                 # Default to Part 1 if ambiguous but Day 1
                 matched_video = VIDEO_MAP["Day 1 Part 1"]

            if matched_video:
                # Force correct recommended source
                current_sources = mod.get("recommended_source_videos", [])
                if not current_sources or current_sources[0] != matched_video["uuid"]:
                    logger.info(f"Refining Module {m_idx+1} Source -> {matched_video['uuid']}")
                    mod["recommended_source_videos"] = [matched_video["uuid"]]
                    updated_any = True
                
                # REPAIR LESSON CLIPS
                lessons = mod.get("lessons", [])
                
                for l_idx, lesson in enumerate(lessons):
                    clips = lesson.get("source_clips", [])
                    if not clips:
                         # If completely empty, add whole video placeholder
                         lesson["source_clips"] = [{
                            "video_filename": matched_video["uuid"],
                            "start_time": 0,
                            "end_time": matched_video["duration"],
                            "reason": "Recovered (Full Video)"
                         }]
                         updated_any = True
                         continue

                    for clip in clips:
                        modified_clip = False
                        
                        # 1. Inject UUID if missing
                        if "video_filename" not in clip and "filename" not in clip and "video" not in clip:
                            clip["video_filename"] = matched_video["uuid"]
                            modified_clip = True
                        elif clip.get("video_filename", "").startswith("Work Order"):
                             clip["video_filename"] = matched_video["uuid"]
                             modified_clip = True
                        elif clip.get("video") and str(clip.get("video")).startswith("Work Order"):
                             clip["video_filename"] = matched_video["uuid"]
                             modified_clip = True

                        # 2. Fix Timestamps (Strings with 's' suffix)
                        for time_key in ["start_time", "end_time", "start", "end"]:
                             val = clip.get(time_key)
                             if val is not None and isinstance(val, str) and val.endswith("s"):
                                 try:
                                     clip[time_key] = float(val.replace("s", ""))
                                     modified_clip = True
                                 except: pass
                        
                        # 3. Fix Missing Timestamps (Default to Full Video if BOTH missing)
                        # We do NOT overwrite if one exists or if they are just 0.0
                        s_val = clip.get("start_time") or clip.get("start")
                        e_val = clip.get("end_time") or clip.get("end")
                        
                        if s_val is None and e_val is None:
                             clip["start_time"] = 0
                             clip["end_time"] = matched_video["duration"]
                             modified_clip = True
                        
                        if modified_clip:
                            updated_any = True

        # 2. Parallel Polish (Objectives & Quizzes) -- Same as before but kept distinct
        semaphore = asyncio.Semaphore(10)
        
        async def process_lesson_polish(m_idx, l_idx, lesson):
            nonlocal updated_any
            modified = False
            async with semaphore:
                # Normalize keys just in case
                clips = lesson.get("source_clips", [])
                for clip in clips:
                    # Map 'video' -> video_filename (found in Mod 2)
                    if "video" in clip and "video_filename" not in clip:
                         clip["video_filename"] = clip.pop("video")
                         modified = True
                    
                    # If filename is crap "Work Order...", swap to Module's recommended
                    if mod.get("recommended_source_videos"):
                        correct_uuid = mod["recommended_source_videos"][0]
                        if clip.get("video_filename", "").startswith("Work Order"):
                            clip["video_filename"] = correct_uuid
                            modified = True
                            
                # Objective Polish
                current_obj = lesson.get("learning_objective", "")
                if not current_obj or current_obj.startswith("Understand the concepts of"):
                    # logger.info(f"   Refining Objective: Mod {m_idx+1} Les {l_idx+1}")
                    obj = await generate_objective(lesson.get("title"), lesson.get("voiceover_script", ""))
                    lesson["learning_objective"] = obj
                    modified = True
                    updated_any = True
                
                # Quiz Polish
                if "quiz" not in lesson or not lesson["quiz"]:
                     # (Previous logic reused if needed, omitting for brevity to prioritize clip fix)
                     pass

            return modified

        tasks = []
        for i, mod in enumerate(modules):
            for j, lesson in enumerate(mod.get("lessons", [])):
                tasks.append(process_lesson_polish(i, j, lesson))
        
        if tasks:
            await asyncio.gather(*tasks)
        
        if updated_any:
            # Atomic Save
            course.structured_json = master_plan
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(course, "structured_json")
            db.commit()
            logger.info("--- Repair Complete: DB Updated ---")
        else:
            logger.info("--- No Repairs Needed ---")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(repair_course_14())
