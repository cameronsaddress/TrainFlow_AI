
import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

db = SessionLocal()
courses = db.query(k_models.HybridCurriculum).order_by(k_models.HybridCurriculum.id.desc()).all()

print(f"Total Hybrid Courses: {len(courses)}")

if courses:
    latest = courses[0]
    print(f"Latest Course ID: {latest.id}")
    print(f"Title: {latest.title}")
    
    # Check structure
    data = latest.structured_json
    modules = data.get("modules", [])
    print(f"Modules: {len(modules)}")
    
    video_matches = 0
    for m in modules:
        for l in m["lessons"]:
            if l.get("source_clips"):
                video_matches += len(l["source_clips"])
                print(f"  - Lesson '{l['title']}' has {len(l['source_clips'])} clips")
                
    print(f"Total Video Matches: {video_matches}")
else:
    print("No courses found.")
    
db.close()
