import sys
from sqlalchemy import text
sys.path.append('/app')
from app.db import SessionLocal

def main():
    db = SessionLocal()
    try:
        # Check Hybrid Course 4
        res = db.execute(text("SELECT structured_json FROM hybrid_curricula WHERE id = 4")).fetchone()
        if not res:
            print("Course 4 not found")
            return
            
        data = res[0]
        total = 0
        enriched = 0
        
        block_types = {}
        
        for m in data.get("modules", []):
            for l in m.get("lessons", []):
                total += 1
                if "content_blocks" in l:
                    has_new = False
                    for b in l["content_blocks"]:
                        t = b.get("type")
                        block_types[t] = block_types.get(t, 0) + 1
                        if t in ["compliance_checklist", "scenario", "quiz"]:
                            has_new = True
                    if has_new:
                        enriched += 1
                        
        print(f"Total Lessons: {total}")
        print(f"Enriched Lessons: {enriched}")
        print(f"Block Types Distribution: {block_types}")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
