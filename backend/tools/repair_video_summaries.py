import sys
import os
import asyncio
import json

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.models import knowledge as k_models
from app.services import llm
from sqlalchemy.orm.attributes import flag_modified

async def manual_summarize(video):
    # Manual Context Build (Safe Limit)
    SAFE_LIMIT = 100000 # 100k chars ~ 25k tokens
    
    transcript = video.transcript_text or ""
    context = ""
    if len(transcript) > SAFE_LIMIT:
        print(f"   ⚠️ Transcript too long ({len(transcript)} chars). Truncating to {SAFE_LIMIT}...", flush=True)
        context = transcript[:SAFE_LIMIT] + "...[TRUNCATED]"
    else:
        context = transcript
        
    prompt = f"""
    Analyze this raw video transcript and generate a detailed Technical Summary.
    
    Video: {video.filename}
    
    TRANSCRIPT:
    {context}
    
    Output a concise summary (500 words max) covering:
    1. Procedures
    2. Tools
    3. Safety
    """
    
    return await llm.generate_text(prompt, model="x-ai/grok-4.1-fast")

async def repair_summaries():
    print("🏥 Starting MANUAL Video Summary Repair for IDs [138, 147]...", flush=True)
    db = SessionLocal()
    
    target_ids = [138, 147]
    
    try:
        for vid_id in target_ids:
            video = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.id == vid_id).first()
            if not video:
                print(f"❌ Video ID {vid_id} not found/skipped.", flush=True)
                continue
                
            print(f"🔄 Generating Summary for {vid_id}: {video.filename}...", flush=True)
            
            try:
                # Call manual summarizer
                summary = await manual_summarize(video)
                
                if not summary:
                    print(f"   ❌ LLM returned empty summary.", flush=True)
                    continue

                print(f"   ✅ Generated Summary ({len(summary)} chars).", flush=True)
                
                # Update DB
                if not video.metadata_json:
                    video.metadata_json = {}
                
                video.metadata_json["summary"] = summary
                
                # Force update
                flag_modified(video, "metadata_json")
                db.commit()
                print(f"   💾 Saved to DB.", flush=True)
                
            except Exception as e:
                print(f"   ❌ Failed to summarize {vid_id}: {e}", flush=True)
                
        print("✨ Repair Complete.", flush=True)
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(repair_summaries())
