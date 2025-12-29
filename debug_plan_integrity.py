
import sys
import json
from sqlalchemy import create_engine, text

# Direct connection via Standard Docker Network URL
DATABASE_URL = "postgresql://user:password@trainflow-db:5432/trainflow"

def check_plan_integrity(plan_id):
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print(f"--- Plan {plan_id} Integrity Check ---")
            
            result = connection.execute(text(f"SELECT structured_json FROM training_curricula WHERE id={plan_id}"))
            row = result.fetchone()
            
            if not row:
                 print(f"❌ Plan {plan_id} NOT FOUND.")
                 return

            plan_json = row[0]
            modules = plan_json.get("modules", [])
            
            print(f"Total Modules: {len(modules)}")
            complete_count = 0
            
            for idx, m in enumerate(modules):
                lessons = m.get("lessons", [])
                count = len(lessons)
                status = "✅ COMPLETE" if count > 0 else "❌ COMPLETED"
                if count > 0: complete_count += 1
                
                print(f"Module {idx+1}: {count} Lessons. {status}")

            print(f"\nSummary: {complete_count}/{len(modules)} Modules have content.")

    except Exception as e:
        print(f"Check Failed: {e}")

if __name__ == "__main__":
    check_plan_integrity(18)
