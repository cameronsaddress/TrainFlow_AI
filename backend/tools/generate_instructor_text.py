import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Setup path
sys.path.append("/app")

load_dotenv()

SOURCE_TEXT = """
POLE SPECIFICATION AND IDENTIFICATION
Distribution poles shall be solid wood, fiberglass (fiber-reinforced polymer), or metal and in accordance with
applicable standards such as ANSI Standard O5.1, Company Material Specifications MS2005, and MS2010.
In general, poles listed on Page 2-101 are used for distribution circuits. However, where taller poles are
required or pole loading is such that larger poles are required, poles traditionally stocked for transmission or
sub-transmission structures may be used. Distribution pole strengths are designated by “Class” 1 through 6.
These classes establish pole circumference minimums. Transmission Class H1 poles are utilized for critical
structures as part of our storm hardening efforts. In NY, Class 1 poles are utilized for main lines and poles
carrying heavy equipment (refer to Section 4 – Storm Hardening and Resiliency).
2.1.10 Pole Numbering
Each pole carrying Company attachments shall be Company identified and individually
numbered on the road-side face of the pole, approximately 7 feet above grade, as shown on
Drawing 2-111. On privately owned poles, which have Company equipment attached, a single
letter “P” shall be installed below the pole number. Main junction and equipment support poles
may also be identified by having the line number placed above the pole number.
Each individual pole line (8 or more poles) shall have poles consecutively numbered beginning
at its origination from the main line. Short branch lines expected to never contain more than
eight poles shall be sub-numbered from the tap pole.
2.1.20 Reflectors
In Massachusetts, pole reflectors (Std Item Z12), mounted vertically facing traffic approximately
4 feet above grade, are required on all poles located on state highways within 6 feet of the
traveled way, not protected by a guardrail. Existing poles, where construction is taking place
and the above requirements are met, shall have reflectors installed. All other states within the
National Grid service territory do not have a reflector requirement, but reflectors may be used
where deemed appropriate.
Reflective Color – On ramps, freeways, divided highways, and one-way streets, reflective
material shall face oncoming traffic and shall be colored white on the right side of the roadway
and yellow on the left side of the roadway. On two-way undivided roadways, reflective material
shall be colored white and shall be placed on poles to the right of, and facing, oncoming traffic
on each side of the road.
2.1.30 Phase and Feeder Numbering
Phase and feeder identification shall be installed on the first pole outside of the substation and
when requested. Phase identification shall be installed and located per construction drawings (2-
112, 2-112A) on all smart technology devices as follows:
a. 3Փ reclosers 3Փ advanced capacitors, 3Փ voltage regulators, and 3Փ feeder monitors.
Prior to any work on multi-phase lines, phase identification shall always be confirmed with proper
testing equipment (e.g. phase tester). Absolute phase relationship can be best identified using
Company approved long distance phasing tools.
2.1.40 Warning Signs
In Massachusetts, all non-wood poles supporting lines operating in excess of 2,000 volts shall
be marked with warning signs “Dangerous, Keep Away.” See Standard ID’s P23B1, P23B2 and
P23B3.
All poles stepped less than six and one-half feet (6.5') from the ground and carrying wires or
cables within a NYS Thruway ROW shall be labeled on both side of the pole with Danger sign
(P23C1 – P23C3).
2.1.50 FAA OBSTRUCTION MARKING AND LIGHTING
Aerial markers and/or lighting may be required for lines installed adjacent to registered airports
as deemed necessary by the FAA Advisory Circular (AC).
"""

async def generate_script():
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("LLM_API_BASE")
    )
    
    sys_prompt = (
        "You are 'Mike', a friendly, experienced Senior Lineman Instructor. "
        "Your goal is to explain the provided technical standard to a new apprentice in a conversational, engaging way. "
        "Don't just read it. TEACH it. "
        "Use phrases like 'Here's what you need to look out for', 'Remember', 'In the field, we usually...'. "
        "Cover ALL the key requirements (Pole types, numbering, reflectors, phase ID, warning signs) but make it flow like a story. "
        "Keep it under 350 words (approx 2 mins spoken)."
    )
    
    print("Generating Instructor Script...")
    response = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "x-ai/grok-4.1-fast"),
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Technical Standard:\n{SOURCE_TEXT}"}
        ],
        temperature=0.3
    )
    
    script = response.choices[0].message.content
    print("\n--- GENERATED SCRIPT ---\n")
    print(script)
    print("\n------------------------\n")
    
    # Save to file for the synthesis step
    with open("/app/tools/lesson_2_script.txt", "w") as f:
        f.write(script)

if __name__ == "__main__":
    asyncio.run(generate_script())
