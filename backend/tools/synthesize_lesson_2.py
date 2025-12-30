from elevenlabs.client import ElevenLabs
from elevenlabs import save
import os
from dotenv import load_dotenv

load_dotenv()

def synthesize():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in env.")
        return

    client = ElevenLabs(api_key=api_key)

    # Load the script
    script_path = "/app/tools/lesson_2_script.txt"
    if not os.path.exists(script_path):
        print(f"Error: Script file {script_path} not found. Run generate_instructor_text.py first.")
        return
        
    with open(script_path, "r") as f:
        text = f.read()

    print("Synthesizing Audio via ElevenLabs...")
    print(f"Text Length: {len(text)} chars")
    
    # Generate audio
    # Using 'Adam' - a popular, warm, American male voice suitable for narration.
    # Voice ID for Adam: "pNInz6obpgDQGcFmaJgB" (Legacy ID) or just name="Adam"
    # The SDK handles names well.
    
    # SDK v3 update: 'generate' is often a standalone function or client.generate
    # We imported 'ElevenLabs' client but also need 'generate' from the module if using the simple API.
    # Let's try the simple API which is robust.
    print(f"Synthesizing Audio via ElevenLabs (Client API)...")
    
    # V3 SDK Pattern: client.text_to_speech.convert
    audio_generator = client.text_to_speech.convert(
        voice_id="pNInz6obpgDQGcFmaJgB", # Adam
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_turbo_v2"
    )
    
    output_path = "lesson_2_instructor.mp3"
    
    # Save generator to file
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)
            
    print(f"SUCCESS: Audio saved to {output_path}")

if __name__ == "__main__":
    synthesize()
