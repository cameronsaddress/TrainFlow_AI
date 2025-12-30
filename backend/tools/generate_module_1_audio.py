import os
import sys
import asyncio
import json
from sqlalchemy import text
from dotenv import load_dotenv
from openai import AsyncOpenAI
from elevenlabs.client import ElevenLabs
# We need to import the correct V3 method if using client
# But since we had issues importing 'generate' directly, let's just use the client we instantiate.

sys.path.append('/app')
from app.db import SessionLocal
from app.models.knowledge import HybridCurriculum, KnowledgeDocument as Document

load_dotenv()

# Configuration
COURSE_ID = 4
MODULE_INDEX = 0  # Section 1 is Module 0
DOC_ID = 10       # The PDF
MAX_PAGES = 40    # Section 1 is usually at the start
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Setup Clients
llm_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_API_BASE")
)

el_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

async def get_pdf_context(db):
    """Fetches the first X pages of the PDF text."""
    doc = db.query(Document).filter(Document.id == DOC_ID).first()
    if not doc or not doc.extracted_text:
        raise Exception("PDF Document not found or empty.")
    
    # Heuristic: ~3000 chars per page? 
    # Let's just grab the first 100k chars to be safe for Section 1.
    return doc.extracted_text[:100000]

async def map_content_to_lessons(context_text, lesson_titles):
    """Asks LLM to find the relevant text for each lesson."""
    
    print(f"Mapping content for {len(lesson_titles)} lessons...")
    
    prompt = f"""
    You are a Curriculum Expert. 
    I have a list of Lesson Titles for "Section 1 - General" of a Distribution Standards Manual.
    I also have the raw text of the manual.
    
    GOAL: For EACH lesson title, find the specific text in the manual that covers that topic.
    
    LESSON TITLES:
    {json.dumps(lesson_titles, indent=2)}
    
    MANUAL TEXT (First 100k chars):
    {context_text}
    
    OUTPUT JSON format:
    {{
        "mappings": [
            {{ "title": "Lesson Title", "relevant_text": "The extracted text from the manual..." }},
            ...
        ]
    }}
    """
    
    response = await llm_client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "x-ai/grok-4.1-fast"),
        messages=[
            {"role": "system", "content": "You are a precise data extractor."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    return json.loads(response.choices[0].message.content).get("mappings", [])

async def generate_script(title, relevant_text):
    """Generates the 'Mike' persona script."""
    print(f"Generating script for: {title}")
    
    sys_prompt = (
        "You are 'Mike', a friendly, experienced Senior Lineman Instructor. "
        "Your goal is to explain the provided technical standard to a new apprentice in a conversational, engaging way. "
        "Don't just read it. TEACH it. "
        "Use phrases like 'Listen up', 'This is critical', 'In the real world...'. "
        "Cover the key points in the text provided. "
        "Keep it concise (under 250 words, ~90 seconds)."
    )
    
    response = await llm_client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "x-ai/grok-4.1-fast"),
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Lesson: {title}\n\nTechnical Source:\n{relevant_text}"}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

def synthesize_audio(text, filename):
    """Synthesizes audio using ElevenLabs Turbo v2."""
    print(f"Synthesizing: {filename}...")
    
    try:
        # V3 Client Method
        audio_generator = el_client.text_to_speech.convert(
            voice_id="pNInz6obpgDQGcFmaJgB", # Adam
            output_format="mp3_44100_128",
            text=text,
            model_id="eleven_turbo_v2"
        )
        
        # Save locally
        # We save to a temp path first, then docker cp later? 
        # No, we are running IN docker if we use docker exec.
        # But wait, this script is being written to HOST. 
        # Ideally we run this inside the container.
        # So the path should be internal.
        
        # We need to save to a place that maps to frontend/public.
        # The container /app maps to backend. 
        # Frontend is separate. 
        # We will save to /app/audio_temp/ and then user can copy.
        
        os.makedirs("/app/audio_temp", exist_ok=True)
        path = f"/app/audio_temp/{filename}"
        
        with open(path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)
        return path
    except Exception as e:
        print(f"Synthesis Error for {filename}: {e}")
        return None

def main():
    db = SessionLocal()
    try:
        # 1. Get Course and Lessons
        course = db.query(HybridCurriculum).filter(HybridCurriculum.id == COURSE_ID).first()
        if not course: 
            print("Course not found")
            return
            
        json_data = course.structured_json
        module = json_data['modules'][MODULE_INDEX]
        lessons = module['lessons']
        lesson_titles = [l['title'] for l in lessons]
        
        # 2. Get PDF Context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        print("Fetching PDF text...")
        pdf_text = loop.run_until_complete(get_pdf_context(db))
        
        # 3. Map Content
        mappings = loop.run_until_complete(map_content_to_lessons(pdf_text, lesson_titles))
        
        # Create a lookup
        map_dict = {m['title']: m['relevant_text'] for m in mappings}
        
        updated = False
        
        # 4. Loop Lessons
        for idx, lesson in enumerate(lessons):
            title = lesson['title']
            print(f"\nProcessing Lesson {idx}: {title}")
            
            # Check if already has audio (optional, but good for restart)
            if lesson.get("instructor_audio"):
                print("Skipping - Audio already exists.")
                continue
                
            source_text = map_dict.get(title)
            if not source_text:
                print("WARNING: No mapped text found. Using title only.")
                source_text = title # Fallback
                
            # Generate Script
            script = loop.run_until_complete(generate_script(title, source_text))
            
            # Synthesize
            # Filename: lesson_{MOD}_{LES}_instructor.mp3
            fname = f"lesson_{MODULE_INDEX}_{idx}_instructor.mp3"
            file_path = synthesize_audio(script, fname)
            
            if file_path:
                # Update JSON
                # The frontend expects a public URL. 
                # We will assume we copy /app/audio_temp -> frontend/public/audio/lessons/
                public_url = f"/audio/lessons/{fname}"
                lesson["instructor_audio"] = public_url
                updated = True
                
        # 5. Commit
        if updated:
            course.structured_json = json_data
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(course, "structured_json")
            db.commit()
            print("\nDatabase updated successfully!")
            print("IMPORTANT: You must now copy files from /app/audio_temp/ to frontend/public/audio/lessons/")
        else:
            print("No changes made.")

    finally:
        db.close()

if __name__ == "__main__":
    main()
