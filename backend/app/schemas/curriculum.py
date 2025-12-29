from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

class SourceClip(BaseModel):
    video_filename: str = Field(..., description="Filename of source video")
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    reason: Optional[str] = Field(default="Demonstrates key concept", description="Why this clip was chosen")

class Lesson(BaseModel):
    title: str = Field(..., description="The title of the lesson")
    voiceover_script: str = Field(..., description="The script for the instructor voiceover")
    learning_objective: Optional[str] = Field(default=None, description="Target Outcome")
    quiz: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Quiz Data")
    source_clips: List[SourceClip] = Field(default_factory=list, description="List of source clips with timestamps")
    smart_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata for compliance and tips")

    @model_validator(mode='before')
    @classmethod
    def validate_source_clips(cls, data: Any) -> Any:
        if isinstance(data, dict):
            clips = data.get('source_clips', [])
            if clips and isinstance(clips, list):
                new_clips = []
                for clip in clips:
                    if isinstance(clip, str):
                        # Recovery Mode: Convert string timestamp to minimal dict (Skip in strict mode? No, allow fallbacks)
                        # Actually strict mode requires video_filename.
                        continue 
                    elif isinstance(clip, dict):
                        # NORMALIZE KEYS
                        if "video_filename" not in clip:
                             if "filename" in clip: clip["video_filename"] = clip["filename"]
                             elif "video" in clip: clip["video_filename"] = clip["video"]
                        
                        if "start_time" not in clip:
                             if "start" in clip: clip["start_time"] = clip["start"]
                        
                        if "end_time" not in clip:
                             if "end" in clip: clip["end_time"] = clip["end"]

                        # CLEAN VALUES (Strings "10s" -> Floats)
                        for k in ["start_time", "end_time"]:
                            if k in clip and isinstance(clip[k], str):
                                try:
                                    clip[k] = float(clip[k].replace("s", ""))
                                except:
                                    clip[k] = 0.0
                        
                        # Check strictness
                        if "video_filename" in clip and "start_time" in clip and "end_time" in clip:
                             new_clips.append(clip)
                
                data['source_clips'] = new_clips
        return data

class Module(BaseModel):
    title: str = Field(..., description="The title of the module")
    description: Optional[str] = Field(default=None, description="A brief overview of the module")
    lessons: List[Lesson] = Field(default_factory=list, description="List of lessons in this module")
    recommended_source_videos: List[str] = Field(default_factory=list, description="List of source video filenames")

class TrainingCurriculum(BaseModel):
    course_title: str = Field(..., description="The overall title of the course")
    course_description: str = Field(..., description="A brief description of the course")
    modules: List[Module] = Field(default_factory=list, description="List of modules in the course")
