
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
from app.models.knowledge import HybridCurriculum, KnowledgeDocument
from app.routers.knowledge import _find_page_for_anchor
from pypdf import PdfReader

# Setup paths
sys.path.append('/app')

# DB Connection
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@trainflow-db:5432/trainflow"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

COURSE_ID = 4
PDF_DOC_ID = 10 

def main():
    db = SessionLocal()
    try:
        print("Fetching Course Data...")
        course = db.query(HybridCurriculum).get(COURSE_ID)
        doc = db.query(KnowledgeDocument).get(PDF_DOC_ID)

        if not course or not doc:
            print("Error: content not found.")
            return

        reader = PdfReader(doc.file_path)
        modules = course.structured_json.get('modules', [])
        updates = 0
        
        print("Starting Smart Bake (Proximity-Based)...")
        
        total = 0
        for m in modules: total += len(m.get('lessons', []))
        
        curr = 0
        for mod in modules:
            mod_title = mod.get('title', '').strip()
            # 1. Find Section Anchor (Baseline)
            section_page = _find_page_for_anchor(reader, mod_title, doc_id=PDF_DOC_ID)
            if section_page == -1: section_page = 1 # Fallback
            
            print(f"\n--- Processing Module: {mod_title} (Starts ~Page {section_page}) ---")
            
            for lesson in mod.get('lessons', []):
                curr += 1
                lesson_title = lesson.get('title', '').strip()
                
                # Candidates to search
                candidates = [lesson_title]
                
                # Derived Candidates
                # 1. Remove "Lesson X:" prefix
                if ":" in lesson_title:
                    candidates.append(lesson_title.split(":", 1)[1].strip())
                
                # 2. Last meaningful Bigram/Trigram (e.g. "Guy Clearances" -> "Clearances")
                words = lesson_title.split()
                if len(words) > 1:
                    candidates.append(" ".join(words[-2:])) # "Guy Clearances"
                if len(words) > 2:
                    candidates.append(" ".join(words[-3:]))
                if len(words) > 0:
                     candidates.append(words[-1]) # "Clearances"
                
                # Remove duplicates
                candidates = list(dict.fromkeys(candidates))
                
                best_page = -1
                best_dist = 9999
                best_anchor = ""
                
                # Search Strategy
                found_something = False
                
                for cand in candidates:
                    if len(cand) < 4: continue # Skip short junk
                    
                    found = _find_page_for_anchor(reader, cand, doc_id=PDF_DOC_ID)
                    
                    if found != -1:
                        # PROXIMITY CHECK
                        # Must be >= section_page (don't go backwards to previous sections)
                        # We want the *smallest* page that meets this criteria (closest to start)
                        if found >= section_page:
                            dist = found - section_page
                            if dist < best_dist:
                                best_dist = dist
                                best_page = found
                                best_anchor = cand
                                found_something = True
                                # Optimization: If distance is small (<10 pages), it's probably right. 
                                # But we iterate all anyway to be safe? No, "Clearances" might be P5, "Guy Clearances" P104.
                                # P5 (dist 1) is better than P104 (dist 100).
                
                # Fallback to Section Page if nothing specific found
                if not found_something:
                     best_page = section_page
                     best_anchor = mod_title
                     match_type = "FALLBACK"
                else:
                     match_type = f"SMART ({best_anchor})"
                
                # Update DB
                if 'pdf_reference' not in lesson or not lesson['pdf_reference']:
                    lesson['pdf_reference'] = {}
                
                old_p = lesson['pdf_reference'].get('page_number')
                if old_p != best_page:
                    lesson['pdf_reference']['page_number'] = best_page
                    lesson['pdf_reference']['anchor_text'] = best_anchor
                    updates += 1
                    print(f"[{curr}/{total}] UPDATE: '{lesson_title}' -> P.{best_page} [{match_type}]")
                else:
                    print(f"[{curr}/{total}] OK: P.{best_page}")

        if updates > 0:
            course.structured_json = {"modules": modules}
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(course, "structured_json")
            db.commit()
            print(f"SUCCESS: Updated {updates} lessons with Smart Logic.")
        else:
            print("No updates needed.")
            
    except Exception as e:
        print(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
