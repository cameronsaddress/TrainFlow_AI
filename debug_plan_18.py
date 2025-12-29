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
        videos = db.query(k_models.VideoCorpus).all()
        db_filenames = {v.filename: v for v in videos}
        
        print(f"Total Videos in DB: {len(videos)}")
        # print(list(db_filenames.keys()))

        print("\n--- Mismatch Analysis ---")
        missing = []
        for f in all_plan_filenames:
            if f not in db_filenames:
                missing.append(f)
                print(f"❌ MISSING in DB: '{f}'")
                
                # Fuzzy Check
                for db_f in db_filenames.keys():
                    if f.lower() in db_f.lower() or db_f.lower() in f.lower():
                         print(f"   -> Did you mean: '{db_f}'?")
            else:
                v = db_filenames[f]
                has_transcript = v.transcript_json is not None or (v.transcript_text and len(v.transcript_text) > 0)
                print(f"✅ FOUND: '{f}' (Transcript: {has_transcript})")

    finally:
        db.close()

if __name__ == "__main__":
    diagnose_plan(18)
