# Use NVIDIA PyTorch container (Verified ARM64 support) as base
FROM nvcr.io/nvidia/pytorch:25.11-py3

WORKDIR /app

# 1. Install System Dependencies (Runtime & Build)
# GB10 Update: Added libsndfile1 (NeMo), libgl1 (CV2), and networking tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libsndfile1 \
    build-essential \
    git \
    cmake \
    ninja-build \
    pkg-config \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 2. Build Torchaudio from Source (Skipped for GB10/NeMo)
# NeMo Toolkit and the NGC container generally provide compatible audio backends.
# Building from 'main' can break against stable container versions.
# ENV USE_FFMPEG=0
# ENV USE_ROCM=0
# RUN git clone https://github.com/pytorch/audio.git /tmp/torchaudio && \
#     cd /tmp/torchaudio && \
#     pip install . --no-deps --no-build-isolation -v && \
#     cd /app && \
#     rm -rf /tmp/torchaudio

# 3. Copy Requirements
COPY requirements.txt .

# 4. Install Safe Python Dependencies
# (These are standard libs like fastapi, pydantic, numpy, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Install Complex AI Libraries with --no-deps
# We do this to strictly PREVENT pip from pulling a CPU-only torch wheel
# which would overwrite the GB10-optimized system torch.
RUN pip install --no-deps \
    transformers \
    ultralytics \
    pyannote.audio \
    openai-whisper \
    speechbrain \
    asteroid-filterbanks

# 6. Copy Application Code
COPY . .

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
