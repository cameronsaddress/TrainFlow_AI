from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

class Lesson(BaseModel):
    title: str = Field(..., description="The title of the lesson")
    voiceover_script: str = Field(..., description="The script for the instructor voiceover")
    source_clips: List[Dict[str, Any]] = Field(default_factory=list, description="List of source clips with timestamps")
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
                        # Recovery Mode: Convert string timestamp to minimal dict
                        new_clips.append({"timestamp": clip, "note": "Recovered from cache"})
                    else:
                        new_clips.append(clip)
                data['source_clips'] = new_clips
        return data

class Module(BaseModel):
    title: str = Field(..., description="The title of the module")
    lessons: List[Lesson] = Field(default_factory=list, description="List of lessons in this module")
    recommended_source_videos: List[str] = Field(default_factory=list, description="List of source video filenames")

class TrainingCurriculum(BaseModel):
    course_title: str = Field(..., description="The overall title of the course")
    course_description: str = Field(..., description="A brief description of the course")
    modules: List[Module] = Field(default_factory=list, description="List of modules in the course")
