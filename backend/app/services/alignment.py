from typing import List, Dict
from ..models.models import TrainingStep

def align_multimodal_data(asr_data: Dict, cv_data: List[Dict]) -> List[Dict]:
    """
    Merge ASR transcript segments with CV detected events based on timestamps.
    Returns a list of aligned 'Step' dictionaries.
    """
    aligned_steps = []
    
    # Simple algorithm: 
    # 1. Iterate through ASR segments (conceptual 'steps' often align with speech pauses)
    # 2. Find CV events that occurred during that segment's time window.
    # 3. Combine checks.
    
    # Note: ASR format from Whisper: {'segments': [{'start': 0.0, 'end': 2.0, 'text': '...'}]}
    
    segments = asr_data.get('segments', [])
    
    for i, seg in enumerate(segments):
        start = seg['start']
        end = seg['end']
        text = seg['text']
        
        # Filter CV events in this window
        relevant_frames = [
            frame for frame in cv_data 
            if start <= frame['timestamp'] <= end
        ]
        
        # Determine best screenshot (middle of segment or where action happens)
        best_screenshot = None
        ui_metadata = {}
        
        if relevant_frames:
            # Pick middle frame
            mid_idx = len(relevant_frames) // 2
            best_frame = relevant_frames[mid_idx]
            
            # If we had real paths, we'd use them. 
            # For now, we assume the CV data might contain S3 paths or base64 (omitted for size).
            best_screenshot = f"frame_{int(best_frame['timestamp'])}.jpg" 
            ui_metadata = best_frame.get('ui_elements', [])

        step = {
            "step_number": i + 1,
            "action_type": "instruction", # Inference needed here (LLM step)
            "action_details": text,
            "start_ts": start,
            "end_ts": end,
            "duration": end - start,
            "screenshot_path": best_screenshot,
            "ui_metadata": ui_metadata,
            "notes": text
        }
        aligned_steps.append(step)
        
    return aligned_steps

def align_precise_timeline(text_steps: List[str], timeline: List[Dict]) -> List[Dict]:
    """
    Intelligently aligns LLM-segmented text steps to the granular ASR timeline.
    Uses 'Anchor Matching' (First/Last words) to find precise start/end timestamps.
    """
    aligned_results = []
    timeline_cursor = 0
    total_words = len(timeline)
    
    import re
    def normalize(text):
        return re.sub(r'[^\w\s]', '', text).lower().split()

    for step_idx, step_text in enumerate(text_steps):
        step_words = normalize(step_text)
        if not step_words:
             # Empty step?
             aligned_results.append({"start_ts": 0, "end_ts": 0, "duration": 0})
             continue
             
        # Find Start Anchor (First 3 words)
        start_anchor = step_words[:3]
        start_ts = None
        start_idx = timeline_cursor
        
        # Search forward from cursor
        for i in range(timeline_cursor, min(timeline_cursor + 500, total_words)): # limit lookahead
             # Check match
             match = True
             for k in range(len(start_anchor)):
                 if i + k >= total_words:
                     match = False
                     break
                 # Fuzzy check: "start" vs "start."
                 tl_word = re.sub(r'[^\w\s]', '', timeline[i+k]['word']).lower()
                 if tl_word != start_anchor[k]:
                     match = False
                     break
             if match:
                 start_ts = timeline[i]['start_ts']
                 start_idx = i
                 break
        
        # If Start Anchor failed, fallback to previous end (Gapless)
        if start_ts is None:
            print(f"Align Warning: Could not find start anchor for step {step_idx+1}: {step_words[:3]}")
            start_ts = aligned_results[-1]['end_ts'] if aligned_results else 0.0
            start_idx = timeline_cursor
            
        # Find End Anchor (Last 3 words)
        end_anchor = step_words[-3:]
        end_ts = None
        end_idx = start_idx
        
        # Search forward from start_idx
        for i in range(start_idx, min(start_idx + 1000, total_words)):
             match = True
             for k in range(len(end_anchor)):
                 if i + k >= total_words:
                     match = False
                     break
                 tl_word = re.sub(r'[^\w\s]', '', timeline[i+k]['word']).lower()
                 if tl_word != end_anchor[k]:
                      match = False
                      break
             if match:
                 # End of the LAST word in anchor
                 last_w_idx = i + len(end_anchor) - 1
                 if last_w_idx < total_words:
                      end_ts = timeline[last_w_idx]['end_ts']
                      end_idx = last_w_idx + 1 # Update cursor to next word
                 break
                 
        if end_ts is None:
             print(f"Align Warning: Could not find end anchor for step {step_idx+1}: {step_words[-3:]}")
             # Estimate duration based on word count
             est_words = len(step_words)
             # Assume 0.3s per word if unknown
             end_ts = start_ts + (est_words * 0.3)
             end_idx = start_idx + est_words # Advance approx
             
        # Clamp
        if end_idx > total_words: end_idx = total_words
        
        # Update Global Cursor
        timeline_cursor = end_idx
        
        aligned_results.append({
            "step_number": step_idx + 1,
            "action_details": step_text,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "duration": end_ts - start_ts,
            "confidence": "high" if (start_ts and end_ts) else "low"
        })
        
    return aligned_results
