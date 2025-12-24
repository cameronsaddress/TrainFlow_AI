from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Lesson(BaseModel):
    title: str = Field(..., description="The title of the lesson")
    voiceover_script: str = Field(..., description="The script for the instructor voiceover")
    source_clips: List[Dict[str, Any]] = Field(default_factory=list, description="List of source clips with timestamps")
    smart_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata for compliance and tips")

class Module(BaseModel):
    title: str = Field(..., description="The title of the module")
    lessons: List[Lesson] = Field(default_factory=list, description="List of lessons in this module")
    recommended_source_videos: List[str] = Field(default_factory=list, description="List of source video filenames")

class TrainingCurriculum(BaseModel):
    course_title: str = Field(..., description="The overall title of the course")
    course_description: str = Field(..., description="A brief description of the course")
    modules: List[Module] = Field(default_factory=list, description="List of modules in the course")
