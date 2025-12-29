import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models
from sqlalchemy.orm.attributes import flag_modified

DOC_ID = 10
COURSE_ID = 4
TARGET_MODULE_TITLE = "Section 1 – General"
TARGET_LESSON_TITLE = "Transmission and Sub-Transmission Voltages"

def main():
    db = SessionLocal()
    try:
        print("--- FALLBACK CONTENT EXTRACTION ---")
        
        # 1. Fetch Data
        course = db.query(k_models.HybridCurriculum).get(COURSE_ID)
        doc = db.query(k_models.KnowledgeDocument).get(DOC_ID)
        full_text = doc.extracted_text
        
        # 2. Extract Content using Regex/Find
        # Look for body text: "This is a list of nominal transmission system voltages"
        start_idx = full_text.find("This is a list of nominal transmission system voltages")
        
        # If found, back up to get the header "1.3..."
        if start_idx != -1:
             start_idx = full_text.rfind("1.3 TRANSMISSION VOLTAGES", 0, start_idx) 
             # And end at "1.5"
             end_idx = full_text.find("1.5 PRIMARY DISTRIBUTION VOLTAGES", start_idx)
             if end_idx == -1: end_idx = start_idx + 4000
        else:
             print("Warning: Content anchor not found. Trying loose search.")
             start_idx = full_text.find("1.3 TRANSMISSION VOLTAGES")
             # Skip the TOC entry (usually short or followed by page num)
             # Try finding the second one?
             idx2 = full_text.find("1.3 TRANSMISSION VOLTAGES", start_idx + 50)
             if idx2 != -1: start_idx = idx2
             end_idx = start_idx + 5000

        if start_idx != -1:
            if end_idx == -1: end_idx = start_idx + 4000
            
            # Capture Content
            print(f"Found section at index {start_idx} to {end_idx}")
            raw_content = full_text[start_idx:end_idx]
            
            # Clean
            # raw_content = raw_content.replace("1.3 TRANSMISSION VOLTAGES", "### Transmission Voltages").strip()
            
            fallback_script = f"""**[AUTOMATED EXTRACTION]**

{raw_content}

*(Note: Data extraction fallback active due to service limits)*"""

            fallback_obj = "Understand the nominal transmission and sub-transmission system voltages used within National Grid."
            
            # 3. Update DB
            struct = course.structured_json
            updated = False
            for m in struct["modules"]:
                # Use loose matching for Module name too
                if "General" in m["title"] or "Section 1" in m["title"]:
                    for l in m["lessons"]:
                        if "Transmission" in l["title"]:
                            print(f"Updating Lesson: {l['title']}")
                            l["voiceover_script"] = fallback_script
                            l["learning_objective"] = fallback_obj
                            l["estimated_reading_time_minutes"] = 5
                            l["status"] = "complete_fallback"
                            updated = True
                            
            if updated:
                course.structured_json = struct
                flag_modified(course, "structured_json")
                db.commit()
                print("SUCCESS: Updated lesson with raw text content.")
            else:
                print("ERROR: Could not find lesson in structure.")

    finally:
        db.close()

if __name__ == "__main__":
    main()
