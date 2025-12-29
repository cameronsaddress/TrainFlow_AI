import sys
import os
import json
from sqlalchemy import create_engine, text

# Direct connection via Standard Docker Network URL
DATABASE_URL = "postgresql://user:password@trainflow-db:5432/trainflow"

def diagnose_plan(plan_id):
    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
        
        print(f"--- Plan {plan_id} Diagnostic ---")
        
        # 1. Fetch Plan
        result = connection.execute(text(f"SELECT title, structured_json FROM training_curricula WHERE id={plan_id}"))
        row = result.fetchone()
        
        if not row:
             print(f"❌ Plan {plan_id} NOT FOUND in 'training_curricula'.")
             return

        title, plan_json = row
        print(f"Plan Title: {title}")
        
        modules = plan_json.get("modules", [])
        all_plan_filenames = set()
        
        for idx, m in enumerate(modules):
            fnames = m.get("recommended_source_videos", [])
            print(f"Module {idx+1} '{m.get('title')}': {fnames}")
            for f in fnames:
                all_plan_filenames.add(f)

        # 2. Fetch Video Corpus
        print("\n--- DB Video Corpus ---")
        result = connection.execute(text("SELECT filename, transcript_text, transcript_json FROM video_corpus"))
        db_videos = result.fetchall()
        
        db_filenames = {}
        for fname, txt, js in db_videos:
             has_t = (txt is not None and len(txt) > 0) or (js is not None)
             db_filenames[fname] = has_t

        print(f"Total Videos in DB: {len(db_filenames)}")

        print("\n--- Mismatch Analysis ---")
        missing_count = 0
        for f in all_plan_filenames:
            if f not in db_filenames:
                missing_count += 1
                print(f"❌ MISSING in DB: '{f}'")
            else:
                status = "✅ Ready" if db_filenames[f] else "⚠️ Found but NO TRANSCRIPT"
                print(f"{status}: '{f}'")
                if not db_filenames[f]:
                     missing_count += 1 # Treat missing transcript as missing data

        if missing_count == 0:
             print("\n✅ DATA INTEGRITY VERIFIED: All source videos exist and have transcripts.")
        else:
             print(f"\n❌ DATA INTEGRITY FAILURE: {missing_count} missing dependencies.")

        connection.close()

    except Exception as e:
        print(f"Diagnostic Failed: {e}")

if __name__ == "__main__":
    diagnose_plan(18)
