
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
        
        print("Starting Smart Bake V3 (Incremental Commit)...")
        
        total = 0
        for m in modules: total += len(m.get('lessons', []))
        
        curr = 0
        total_updates_session = 0
        
        for mod in modules:
            mod_title = mod.get('title', '').strip()
            section_page = _find_page_for_anchor(reader, mod_title, doc_id=PDF_DOC_ID)
            if section_page == -1: section_page = 1 
            
            print(f"\n--- Processing Module: {mod_title} (Starts ~Page {section_page}) ---")
            mod_updates = 0
            
            for lesson in mod.get('lessons', []):
                curr += 1
                lesson_title = lesson.get('title', '').strip()
                candidates = [lesson_title]
                if ":" in lesson_title:
                    candidates.append(lesson_title.split(":", 1)[1].strip())
                words = lesson_title.split()
                if len(words) > 1: candidates.append(" ".join(words[-2:]))
                if len(words) > 0: candidates.append(words[-1])
                candidates = list(dict.fromkeys(candidates))
                
                best_page = -1
                best_dist = 9999
                best_anchor = ""
                found_something = False
                
                for cand in candidates:
                    if len(cand) < 4: continue
                    found = _find_page_for_anchor(reader, cand, doc_id=PDF_DOC_ID)
                    if found != -1:
                        if found >= section_page:
                            dist = found - section_page
                            if dist < best_dist:
                                best_dist = dist
                                best_page = found
                                best_anchor = cand
                                found_something = True
                
                if not found_something:
                     best_page = section_page
                     best_anchor = mod_title
                     match_type = "FALLBACK"
                else:
                     match_type = f"SMART ({best_anchor})"
                
                if 'pdf_reference' not in lesson or not lesson['pdf_reference']:
                    lesson['pdf_reference'] = {}
                
                old_p = lesson['pdf_reference'].get('page_number')
                # Strict update: If it matches our new best_page, update it.
                if old_p != best_page:
                    lesson['pdf_reference']['page_number'] = best_page
                    lesson['pdf_reference']['anchor_text'] = best_anchor
                    mod_updates += 1
                    total_updates_session += 1
                    print(f"[{curr}/{total}] UPDATE: '{lesson_title}' -> P.{best_page} [{match_type}]")
                else:
                    print(f"[{curr}/{total}] OK: P.{best_page}")

            # Commit per module to ensure progress is saved
            if mod_updates > 0:
                course.structured_json = {"modules": modules}
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(course, "structured_json")
                db.commit()
                # Refresh might be needed? No, session handles it.
                print(f"   Saved {mod_updates} updates for Module.")

        print(f"SUCCESS: Total {total_updates_session} updates completed.")

    except Exception as e:
        print(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
