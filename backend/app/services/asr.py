import os
import torch
import subprocess
import json

# GB10 Optimization: NeMo Toolkit
try:
    import nemo.collections.asr as nemo_asr
    HAS_NEMO = True
except ImportError:
    print("WARNING: NeMo Toolkit not found. ASR and Diarization will fail.")
    HAS_NEMO = False

# Global Singleton
_asr_model = None

def get_asr_model():
    global _asr_model
    if _asr_model is None and HAS_NEMO:
        print("Loading NeMo Parakeet-CTC-1.1B on GB10...")
        # Automatic download from NGC
        # map_location='cuda' ensures it loads on GPU
        _asr_model = nemo_asr.models.EncDecCTCModelBPE.from_pretrained(
            model_name="nvidia/parakeet-ctc-1.1b"
        )
        if torch.cuda.is_available():
            _asr_model = _asr_model.cuda()
            
        # AI Director 2.0: Enable Timestamp Computation
        try:
             cfg = _asr_model.cfg.decoding
             cfg.preserve_alignments = True
             cfg.compute_timestamps = True
             _asr_model.change_decoding_strategy(cfg)
             print("ASR Config: Timestamps Enabled.")
        except Exception as e:
             print(f"Failed to enable timestamp computation: {e}")
             
    return _asr_model

def extract_audio(video_path: str, output_path: str):
    """
    Extract WAV audio from Video using ffmpeg (Standard).
    """
    try:
        # -ac 1: Mono
        # -ar 16000: 16Khz (Standard for NeMo/ASR)
        command = [
            "ffmpeg", "-y", 
            "-i", video_path, 
            "-vn", 
            "-acodec", "pcm_s16le", 
            "-ac", "1", 
            "-ar", "16000", 
            output_path
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg extraction failed: {e}")
        return None

def process_asr(video_path: str):
    """
    GB10 Pipeline: Video -> FFmpeg(WAV) -> NeMo Parakeet (ASR)
    """
    temp_audio = video_path.replace(".mp4", ".wav")
    
    # 1. Extract Audio
    if not extract_audio(video_path, temp_audio):
        return {"segments": [], "text": "Audio Extraction Failed"}
        
    model = get_asr_model()
    if not model:
        return {"segments": [], "text": "NeMo Unavailable"}
        
    # 2. Transcribe
    # NeMo expects list of paths
    print(f"Transcribing {temp_audio}...")
    try:
        # Optimization: Use greedy_batch for speed
        if hasattr(model, 'change_decoding_strategy'):
            try:
                model.change_decoding_strategy(decoding_cfg={"strategy": "greedy_batch"})
            except:
                pass # Fallback if model doesn't support dynamic switch

        with torch.no_grad():
            # transcribe returns list of Hypothesis objects (if return_hypotheses=True)
            # DGX Spark (GB10) has 128GB Unified Memory. Parakeet 1.1B is tiny.
            # Increasing batch_size to 64 to saturate the 1000 TOPS Blackwell GPU.
            hypotheses = model.transcribe([temp_audio], batch_size=64, verbose=False, return_hypotheses=True)
            
            # 4. Format Result with Timeline
            full_text = ""
            timeline = []
            
            if isinstance(hypotheses, list) and len(hypotheses) > 0:
                hyp = hypotheses[0]
                # Handle raw string case (legacy) vs Hypothesis object
                if isinstance(hyp, str):
                    full_text = hyp
                else:
                    full_text = hyp.text
                    
                    # Extract Timeline if available
                    if hasattr(hyp, 'timestamp') and hasattr(hyp, 'tokens'):
                        timeline = _reconstruct_timeline(hyp)
            
            # 3. Diarization (FR-5)
            speaker_segments = []
            try:
                speaker_segments = process_diarization(temp_audio)
                print(f"Diarization Complete: Found {len(speaker_segments)} segments")
            except:
                pass

            # Cleanup
            if os.path.exists(temp_audio):
                 os.remove(temp_audio)

            return {
                "text": full_text,
                "timeline": timeline, 
                "speaker_segments": speaker_segments,
                "segments": [{
                    "start": 0.0,
                    "end": 999.0,
                    "text": full_text,
                    "speaker": "System"
                }],
                "language": "en"
            }
            
    except Exception as e:
        print(f"NeMo Transcription Failed: {e}")
        return {"segments": [], "text": "Transcription Error", "timeline": []}

def get_diarizer_config(output_dir):
    """
    Generate a minimal Hydra-compatible config for ClusteringDiarizer.
    """
    from omegaconf import OmegaConf
    return OmegaConf.create({
        "name": "ClusterDiarizer",
        "num_workers": 0,
        "sample_rate": 16000,
        "batch_size": 16,
        "device": "cuda" if torch.cuda.is_available() else "cpu", 
        "verbose": False, # Fix: NeMo expects this attribute
        "diarizer": {
            "manifest_filepath": "?",
            "out_dir": output_dir,
            "oracle_vad": False,
            "collar": 0.25,
            "ignore_overlap": True,
            "vad": {
                "model_path": "vad_multilingual_marblenet",
                "parameters": {
                    "onset": 0.8, 
                    "offset": 0.6, 
                    "min_duration_on": 0.2, 
                    "min_duration_off": 0.1, 
                    "filter_speech_first": True,
                    "window_length_in_sec": 0.63, # Required for Marblenet
                    "shift_length_in_sec": 0.08,
                    "smoothing": False,
                    "overlap": 0.5 # Fix: Required for Marblenet
                },
            },
            "speaker_embeddings": {
                "model_path": "titanet_large",
                "parameters": {"window_length_in_sec": 1.5, "shift_length_in_sec": 0.75, "multiscale_weights": [1,1,1,1,1], "save_embeddings": False},
            },
            "clustering": {
                "parameters": {"max_num_speakers": 4}
            }
        }
    })

def process_diarization(audio_path: str):
    """
    FR-5: Perform Speaker Diarization.
    Returns list of {start, end, speaker} segments.
    """
    if not HAS_NEMO: return []
    
    import shutil
    from nemo.collections.asr.models import ClusteringDiarizer
    
    # Needs a manifest file
    work_dir = os.path.dirname(audio_path)
    manifest_path = os.path.join(work_dir, "input_manifest.json")
    
    meta = {
        "audio_filepath": audio_path, 
        "offset": 0, 
        "duration": None, 
        "label": "infer", 
        "text": "-", 
        "num_speakers": None, 
        "rttm_filepath": None, 
        "uids": None
    }
    with open(manifest_path, 'w') as f:
        json.dump(meta, f)
        f.write('\n')
        
    try:
        print(f"Running Diarization on {audio_path}...")
        cfg = get_diarizer_config(work_dir)
        cfg.diarizer.manifest_filepath = manifest_path
        
        diarizer = ClusteringDiarizer(cfg=cfg)
        
        # This runs VAD -> Embeddings -> Clustering
        diarizer.diarize()
        
        # Parse RTTM output
        # RTTM format: SPEAKER <file> <channel> <start> <duration> <NA> <NA> <speaker> <NA> <NA>
        rttm_file = os.path.join(work_dir, "pred_rttm", os.path.basename(audio_path).replace(".wav", ".rttm"))
        
        segments = []
        if os.path.exists(rttm_file):
            with open(rttm_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) > 7 and parts[0] == "SPEAKER":
                        start = float(parts[3])
                        dur = float(parts[4])
                        speaker = parts[7]
                        segments.append({
                            "start": start,
                            "end": start + dur,
                            "speaker": speaker
                        })
        return segments
                        
    except Exception as e:
        print(f"Diarization Failed: {e}")
        return []


def _reconstruct_timeline(hyp):
    """
    Reconstruct word-level timestamps from NeMo Hypotheses.
    Robustly handles 'Native Word Timestamps' (Dict) and 'Token Reconstruction' (Legacy).
    """
    try:
        timeline = []
        
        # Strategy 1: Native Word Timestamps (NeMo 1.20+)
        # hyp.timestamp might be a dict like {'word': [{'word': 'hello', 'start_offset': 0.1, 'end_offset': 0.5}, ...]}
        timestamps_attr = getattr(hyp, 'timestamp', None)
        
        if isinstance(timestamps_attr, dict) and 'word' in timestamps_attr:
             # Extract from native dict
             words = timestamps_attr.get('word', [])
             if words:
                 for w_obj in words:
                      # Handle if w_obj is dict or simple object
                      w_text = w_obj.get('word') if isinstance(w_obj, dict) else getattr(w_obj, 'word', "")
                      w_start = w_obj.get('start_offset') if isinstance(w_obj, dict) else getattr(w_obj, 'start_offset', 0.0)
                      w_end = w_obj.get('end_offset') if isinstance(w_obj, dict) else getattr(w_obj, 'end_offset', 0.0)
                      
                      timeline.append({
                          "word": w_text,
                          "start_ts": w_start,
                          "end_ts": w_end
                      })
                 return timeline

        # Strategy 2: Token Level Reconstruction
        tokens = getattr(hyp, 'tokens', [])
        if tokens is None: tokens = [] # Safety check for NoneType
        
        # Access timestamps/durations safely
        # Note: timestamps_attr might be LIST of floats if not a dict (Legacy)
        tk_timestamps = timestamps_attr if isinstance(timestamps_attr, list) else []
        tk_durations = getattr(hyp, 'token_duration', [])
        if tk_durations is None: tk_durations = []
        
        current_word = ""
        word_start = 0.0
        
        for i, token in enumerate(tokens):
            ts = tk_timestamps[i] if i < len(tk_timestamps) else 0.0
            dur = tk_durations[i] if i < len(tk_durations) else 0.0
            
            # SentencePiece/BPE ' ' marker
            is_start_of_word = token.startswith(" ") or token.startswith(" ")
            cleaned_token = token.replace(" ", "").replace(" ", "")
            
            if is_start_of_word:
                if current_word:
                    timeline.append({
                        "word": current_word,
                        "start_ts": word_start,
                        "end_ts": ts
                    })
                current_word = cleaned_token
                word_start = ts
            else:
                current_word += cleaned_token
                
        if current_word:
             timeline.append({
                "word": current_word,
                "start_ts": word_start,
                "end_ts": word_start + 0.5 # Estimate end
            })
            
        return timeline
    except Exception as e:
        print(f"Timeline reconstruction failed: {e}")
        return []
