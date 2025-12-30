import sys
import os
import json
import argparse
from typing import List, Dict, Any

sys.path.append("/app")

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services.llm import repair_cutoff_json
from sqlalchemy.orm.attributes import flag_modified

# --- Configuration ---
COURSE_ID = 4
DUMP_DIR = "/app/dumps"

def validate_table_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures table block matches the backend schema.
    Backend now expects 'rows' to be List[List[str]].
    """
    if block.get("type") != "table":
        return block
    
    rows = block.get("rows", [])
    fixed_rows = []
    
    for r in rows:
        if isinstance(r, list):
            # Perfect, it's a list of strings
            fixed_rows.append([str(c) for c in r])
        elif isinstance(r, dict) and "values" in r:
            # Old format: {'values': [...]}
            fixed_rows.append([str(c) for c in r["values"]])
        else:
            # Fallback for unexpected format (e.g. string)
            print(f"Warning: Dropping malformed row in table '{block.get('title')}': {r}")
            
    block["rows"] = fixed_rows
    return block

def validate_alert_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures alert block has valid type.
    """
    if block.get("type") != "alert":
        return block
        
    valid_types = ["safety", "compliance", "critical_info", "tip", "warning"]
    if block.get("alert_type") not in valid_types:
        print(f"Warning: Coercing invalid alert_type '{block.get('alert_type')}' to 'warning'")
        block["alert_type"] = "warning"
        
    return block

def clean_content_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for b in blocks:
        if b.get("type") == "table":
            cleaned.append(validate_table_block(b))
        elif b.get("type") == "alert":
            cleaned.append(validate_alert_block(b))
        else:
            cleaned.append(b)
    return cleaned

def consume_dump(module_index: int):
    print(f"--- STARTING CONSUMPTION: Module Index {module_index} ---")
    
    # 1. Read File
    filename = f"module_{module_index}_dump.txt"
    filepath = os.path.join(DUMP_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"Error: Dump file not found: {filepath}")
        return

    print(f"Reading {filepath}...")
    with open(filepath, "r") as f:
        raw_content = f.read()

    # 2. Repair & Parse
    print("Repairing JSON...")
    fixed_json = repair_cutoff_json(raw_content)
    
    try:
        data = json.loads(fixed_json)
    except json.JSONDecodeError:
        print("Standard repair failed. Attempting aggressive salvage...")
        try:
            # Aggressive salvage: Remove last incomplete line/object and try to close
            # Find the last closing '} or ']'
            last_rbrace = raw_content.rfind('}')
            last_rbracket = raw_content.rfind(']')
            
            cutoff = max(last_rbrace, last_rbracket)
            if cutoff > 0:
                salvaged = raw_content[:cutoff+1]
                # Close arrays/objects if needed - simplistic approach:
                # If it looks like we are inside the 'lessons' array, add ']}'
                # This is heuristic.
                if salvaged.strip().endswith('}'):
                    salvaged += "]}" 
                
                # Try repair on the truncated version
                fixed_json = repair_cutoff_json(salvaged)
                data = json.loads(fixed_json)
                print("Aggressive salvage successful.")
            else:
                raise Exception("No valid JSON structure found to salvage.")
        except Exception as e:
            print(f"CRITICAL: Failed to parse JSON after salvage: {e}")
            return

    generated_lessons = data.get("lessons", [])
    print(f"Parsed {len(generated_lessons)} lessons from dump.")

    # 3. Update Database
    db = SessionLocal()
    try:
        course = db.query(k_models.HybridCurriculum).get(COURSE_ID)
        modules = course.structured_json.get("modules", [])
        
        if module_index >= len(modules):
            print(f"Error: Module index {module_index} out of range.")
            return

        target_mod = modules[module_index]
        print(f"Target Module in DB: {target_mod['title']}")
        
        # Create map of generated content
        gen_map = {}
        for l in generated_lessons:
            # key by lowercase title for fuzzy matching
            key = l.get("target_lesson_title", "").lower().strip()
            gen_map[key] = l

        updates_count = 0
        
        for db_lesson in target_mod.get("lessons", []):
            db_title_key = db_lesson["title"].lower().strip()
            
            # Match
            match = gen_map.get(db_title_key)
            
            # Fuzzy fallback loop if exact match fails
            if not match:
                for k, v in gen_map.items():
                    if k in db_title_key or db_title_key in k:
                        match = v
                        print(f"Fuzzy match: '{db_lesson['title']}' <-> '{v.get('target_lesson_title')}'")
                        break
            
            if match:
                print(f"Updating: {db_lesson['title']}")
                
                # Fields to update
                db_lesson["status"] = "complete"
                db_lesson["voiceover_script"] = match.get("voiceover_summary", "")
                db_lesson["learning_objective"] = match.get("learning_objective", "")
                db_lesson["estimated_reading_time_minutes"] = match.get("estimated_reading_time_minutes", 5)
                db_lesson["key_takeaways"] = match.get("key_takeaways", [])
                
                # Content Blocks (with validation)
                raw_blocks = match.get("content_blocks", [])
                db_lesson["content_blocks"] = clean_content_blocks(raw_blocks)
                
                updates_count += 1
            else:
                print(f"SKIPPED: No generated content found for '{db_lesson['title']}'")

        if updates_count > 0:
            print(f"Committing {updates_count} updates to DB...")
            
            # Update the JSON structure in the object
            modules[module_index] = target_mod
            course.structured_json["modules"] = modules 
            
            # Explicitly flag modified because it's a JSON column mutation
            flag_modified(course, "structured_json")
            
            db.commit()
            print("SUCCESS: Database updated.")
        else:
            print("No updates applied.")

    except Exception as e:
        print(f"Database Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--module-index", type=int, required=True)
    args = parser.parse_args()
    
    consume_dump(args.module_index)
