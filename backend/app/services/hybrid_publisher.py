
from sqlalchemy.orm import Session
from ..models import knowledge as k_models
import json

def publish_course(db: Session, source_id: int) -> k_models.HybridCurriculum:
    """
    Copies data from TrainingCurriculum (Course 14/23) to the new HybridCurriculum table.
    Performs 'Hydration' of metadata.
    """
    # 1. Fetch Source
    source = db.query(k_models.TrainingCurriculum).get(source_id)
    if not source:
        raise ValueError(f"Source Course {source_id} not found")
        
    data = source.structured_json
    if not data or "modules" not in data:
        raise ValueError("Invalid source structure")
        
    # 2. Calculate Stats
    modules = data.get("modules", [])
    total_mod = len(modules)
    total_less = 0
    total_dur = 0.0
    
    for m in modules:
        lessons = m.get("lessons", [])
        total_less += len(lessons)
        for l in lessons:
            # Try to get estimated time from smart_context or default
            duration = 0
            if "smart_context" in l and "estimated_reading_time" in l["smart_context"]:
                duration = l["smart_context"]["estimated_reading_time"]
            elif "estimated_reading_time_minutes" in l:
                duration = l["estimated_reading_time_minutes"]
                
            total_dur += float(duration or 5.0) # Default 5 mins
            
    # 3. Create Entry
    published = k_models.HybridCurriculum(
        original_curriculum_id=source.id,
        title=source.title,
        description=data.get("course_description", ""),
        structured_json=data,
        total_modules=total_mod,
        total_lessons=total_less,
        total_duration_minutes=total_dur
    )
    
    db.add(published)
    db.commit()
    db.refresh(published)
    return published
