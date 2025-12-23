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

# Ephemeral Model Session
import gc

class ASRModelSession:
    def __init__(self):
        self.model = None

    def __enter__(self):
        if not HAS_NEMO: return None
        print("Loading NeMo Parakeet-CTC-1.1B (Ephemeral)...", flush=True)
        try:
            self.model = nemo_asr.models.EncDecCTCModelBPE.from_pretrained(
                model_name="nvidia/parakeet-ctc-1.1b"
            )
            if torch.cuda.is_available():
                self.model = self.model.cuda()
            
            # AI Director 2.0: Enable Timestamp Computation
            cfg = self.model.cfg.decoding
            cfg.preserve_alignments = True
            cfg.compute_timestamps = True
            self.model.change_decoding_strategy(cfg)
            return self.model
        except Exception as e:
            print(f"Failed to load NeMo Model: {e}", flush=True)
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.model:
            print("Unloading NeMo Model (Cleaning VRAM)...", flush=True)
            del self.model
            self.model = None
        # Aggressive Cleanup
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

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

def get_audio_duration(file_path):
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        return float(result.stdout)
    except:
        return 0.0

def process_long_form_asr(video_path: str, model):
    """
    Robustly handles large files by slicing them into 5-minute chunks, 
    transcribing them individually, and stitching the results.
    """
    import shutil
    import glob
    
    chunk_len_sec = 300 # 5 minutes
    temp_dir = video_path + "_chunks"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 1. Split Audio via FFmpeg
        print(f"Splitting audio into {chunk_len_sec}s chunks...", flush=True)
        # Using segment muxer for fast splitting without re-encoding overhead if possible, 
        # but for consistent WAV input we use standard output
        temp_pattern = os.path.join(temp_dir, "chunk_%03d.wav")
        
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, 
            "-f", "segment", 
            "-segment_time", str(chunk_len_sec), 
            "-c", "copy", 
            temp_pattern
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        chunk_files = sorted(glob.glob(os.path.join(temp_dir, "chunk_*.wav")))
        print(f"Created {len(chunk_files)} chunks. Starting Batch Transcription...", flush=True)

        full_text = ""
        full_timeline = []
        
        # 2. Transcribe in Batches
        # We process chunks in a list. NeMo handles the batching internally.
        # batch_size=4 is extremely safe for 5-minute chunks on GB10 (approx 5GB VRAM usage)
        
        # Note: timestamps are relative to each chunk. We must offset them.
        # We cannot simply pass the whole list to transcribe if we want to fix timestamps easily per file.
        # However, calling transcribe() multiple times (once per chunk) is safer for tracking offsets.
        
        for i, chunk_file in enumerate(chunk_files):
            offset_seconds = i * chunk_len_sec
            
            with torch.no_grad():
                # Transcribe single chunk
                hypotheses = model.transcribe([chunk_file], batch_size=1, verbose=False, return_hypotheses=True)
                
            if hypotheses and len(hypotheses) > 0:
                hyp = hypotheses[0]
                text_segment = hyp.text if hasattr(hyp, 'text') else str(hyp)
                
                # Stitch Text
                full_text += text_segment + " "
                
                # Stitch Timeline (Offsetting)
                if hasattr(hyp, 'timestamp') and hasattr(hyp, 'tokens'):
                    chunk_timeline = _reconstruct_timeline(hyp)
                    for item in chunk_timeline:
                        item['start_ts'] += offset_seconds
                        item['end_ts'] += offset_seconds
                        full_timeline.extend(chunk_timeline)
            
            # Interactive Progress
            if i % 5 == 0:
                print(f"Processed Chunk {i+1}/{len(chunk_files)}...", flush=True)

        print(f"Long-Form Transcription Complete. Total Length: {len(full_text)} chars", flush=True)
        return full_text.strip(), make_serializable(full_timeline)

    finally:
        # Cleanup chunks
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def process_asr(video_path: str):
    """
    GB10 Pipeline: Video -> FFmpeg(WAV) -> NeMo Parakeet (ASR)
    """
    temp_audio = video_path.replace(".mp4", ".wav")
    
    # 1. Extract Audio
    if not extract_audio(video_path, temp_audio):
        return {"segments": [], "text": "Audio Extraction Failed"}
        
    full_text = ""
    timeline = []
    
    try:
        # 2. Transcribe (Ephemeral Scope - ASR ONLY)
        with ASRModelSession() as model:
            if not model:
                print("ASR Model failed to load.")
            else:
                # Decide Strategy based on Duration
                duration = get_audio_duration(temp_audio)
                print(f"Audio Duration: {duration:.2f}s", flush=True)
                
                if duration > 300: # > 5 minutes -> Use Chunking Strategy
                    print("Large File Detected. Switching to Chunked Inference...", flush=True)
                    full_text, timeline = process_long_form_asr(temp_audio, model)
                else:
                    # Short File -> Standard Inference
                    print(f"Transcribing {temp_audio} (Single Pass)...", flush=True)
                    try:
                        if hasattr(model, 'change_decoding_strategy'):
                            try:
                                model.change_decoding_strategy(decoding_cfg={"strategy": "greedy_batch"})
                            except: pass 
                            
                        with torch.no_grad():
                             hypotheses = model.transcribe([temp_audio], batch_size=1, verbose=False, return_hypotheses=True)
                             if hypotheses:
                                 hyp = hypotheses[0]
                                 full_text = hyp.text
                                 timeline = _reconstruct_timeline(hyp)
                    except Exception as asr_e:
                        print(f"NeMo Transcription Inner Failed: {asr_e}", flush=True)
                        full_text = "Transcription Error"

        # 3. Diarization (FR-5) - STARTING NEW SCOPE
        # ASR Model is strictly unloaded here due to 'with' block exit
        speaker_segments = []
        try:
            if os.path.exists(temp_audio):
                 # process_diarization loads its own models (Titanet)
                 speaker_segments = process_diarization(temp_audio)
                 print(f"Diarization Complete: Found {len(speaker_segments)} segments", flush=True)
        except Exception as d_e:
            print(f"Diarization Failed: {d_e}", flush=True)

        return make_serializable({
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
        })
            
    except Exception as e:
        print(f"Global ASR Process Failed: {e}", flush=True)
        return {"segments": [], "text": "Global Error", "timeline": []}
    finally:
        # Cleanup
        if os.path.exists(temp_audio):
             try:
                 os.remove(temp_audio)
             except: pass

def make_serializable(obj):
    """
    Recursively convert numpy/torch types to native Python types for JSON serialization.
    """
    import numpy as np
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(v) for v in obj]
    elif hasattr(obj, 'item'): # numpy/torch scalars
        return obj.item()
    elif hasattr(obj, 'tolist'): # numpy/torch arrays
        return obj.tolist()
    else:
        return obj

def get_diarizer_config(output_dir):
    """
    Generate a minimal Hydra-compatible config for ClusteringDiarizer.
    Includes all necessary default parameters to pass NeMo's strict validation.
    """
    from omegaconf import OmegaConf
    return OmegaConf.create({
        "name": "ClusterDiarizer",
        "num_workers": 0,
        "sample_rate": 16000,
        "batch_size": 16,
        "device": "cuda" if torch.cuda.is_available() else "cpu", 
        "verbose": False, 
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
                    "window_length_in_sec": 0.63, 
                    "shift_length_in_sec": 0.08,
                    "smoothing": False,
                    "overlap": 0.5 
                },
            },
            "speaker_embeddings": {
                "model_path": "titanet_large",
                "parameters": {
                    "window_length_in_sec": 1.5, 
                    "shift_length_in_sec": 0.75, 
                    "multiscale_weights": [1,1,1,1,1], 
                    "save_embeddings": False
                },
            },
            "clustering": {
                "parameters": {
                    "max_num_speakers": 4,
                    "oracle_num_speakers": False,
                    "max_rp_threshold": 0.25,
                    "sparse_search_volume": 30,
                    "maj_vote_spk_count": False # Common default
                }
            },
            "msdd_model": { # Sometimes required even if not used
                 "model_path": "diar_msdd_telephonic",
                 "parameters": {
                     "use_speaker_model_from_ckpt": True,
                     "infer_batch_size": 25,
                     "sigmoid_threshold": [0.7],
                     "seq_eval_mode": False,
                     "split_infer": True,
                     "diar_window_length": 50,
                     "overlap_infer": 10
                 }
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
