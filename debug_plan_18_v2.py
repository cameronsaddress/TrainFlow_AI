import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from app.database import SessionLocal
from app import models as k_models
import json

def diagnose_plan(plan_id):
    db = SessionLocal()
    try:
        # Load Plan
        plan = db.query(k_models.TrainingCurriculum).get(plan_id)
        if not plan:
            print(f"Plan {plan_id} not found.")
            return

        print(f"--- Plan {plan_id}: {plan.title} ---")
        modules = plan.structured_json.get("modules", [])
        
        all_plan_filenames = set()
        for idx, m in enumerate(modules):
            fnames = m.get("recommended_source_videos", [])
            print(f"Module {idx+1} '{m.get('title')}': {fnames}")
            for f in fnames:
                all_plan_filenames.add(f)

        print("\n--- DB Video Corpus ---")
        # Just grab filenames to be fast
        video_rows = db.query(k_models.VideoCorpus.filename, k_models.VideoCorpus.transcript_text, k_models.VideoCorpus.transcript_json).all()
        db_filenames = {}
        for fname, txt, js in video_rows:
            db_filenames[fname] = (txt is not None and len(txt) > 0) or (js is not None)

        print(f"Total Videos in DB: {len(db_filenames)}")
        
        print("\n--- Mismatch Analysis ---")
        missing = []
        for f in all_plan_filenames:
            if f not in db_filenames:
                missing.append(f)
                print(f"❌ MISSING in DB: '{f}'")
                
                # Fuzzy Check
                found_fuzzy = False
                for db_f in db_filenames.keys():
                    if f.lower() == db_f.lower():
                         print(f"   -> Case Mismatch! DB has: '{db_f}'")
                         found_fuzzy = True
                    elif f.replace(".mp4","") == db_f.replace(".mp4",""):
                         print(f"   -> Extension Mismatch! DB has: '{db_f}'")
                         found_fuzzy = True
                
                if not found_fuzzy:
                    print(f"   -> No obvious fuzzy match.")
            else:
                has_transcript = db_filenames[f]
                status = "✅ Ready" if has_transcript else "⚠️ Found but NO TRANSCRIPT"
                print(f"{status}: '{f}'")

    finally:
        db.close()

if __name__ == "__main__":
    diagnose_plan(18)
