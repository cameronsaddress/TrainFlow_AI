import os
import sys

print("--- 1. Checking NVIDIA NeMo ---")
try:
    import nemo
    import nemo.collections.asr as nemo_asr
    print("SUCCESS: NeMo imported.")
except ImportError as e:
    print(f"FAILURE: NeMo missing: {e}")

print("\n--- 2. Checking GPU/CUDA ---")
try:
    import torch
    print(f"Torch Version: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device: {torch.cuda.get_device_name(0)}")
    else:
        print("FAILURE: No CUDA detected.")
except ImportError:
    print("FAILURE: Torch missing.")

print("\n--- 3. Checking MoviePy + NVENC (Simulated) ---")
try:
    from moviepy.config import get_setting
    print(f"MoviePy FFmpeg Binary: {get_setting('FFMPEG_BINARY')}")
    # We can't easily test NVENC without a video, but we verify module exists
    import moviepy.editor as mp
    print("SUCCESS: MoviePy imported.")
except Exception as e:
    print(f"FAILURE: MoviePy issue: {e}")

print("\n--- 4. Checking DALI ---")
try:
    import nvidia.dali as dali
    print("SUCCESS: DALI imported.")
except ImportError:
    print("FAILURE: DALI missing. (This might be expected if only installed in specific env)")

print("\n--- End Verification ---")
