# TrainFlow AI: GB10 Migration & Optimization Plan

## Objective
Migrate `TrainFlow_AI` from a CPU-heavy/mixed architecture to a **Grace Blackwell (GB10) Optimized** stack.
This plan focuses on maximizing hardware utilization (NVDEC, Tensor Cores, NVLink) using NVIDIA's "Best Practice" libraries.

## 1. Architecture Overhaul

### Current State
*   **Video Decoding:** CPU (`ffmpeg`, `cv2`).
*   **OD/OCR:** Standard PyTorch/Tesseract (`YOLOv8x`, `pytesseract`).
*   **ASR:** `faster-whisper` (Optimized, but not native NeMo/Parakeet).
*   **LLM:** External API (Mocked OpenAI).

### Target GB10 State
*   **Video Ingestion:** **NVIDIA DALI** (Zero-Copy GPU Decoding).
*   **Object Detection:** **TensorRT** Compiled `YOLO-World` (Open Vocabulary).
*   **OCR:** **PaddleOCR** (GPU-accelerated) or NIM.
*   **ASR:** **NVIDIA NeMo** (`Parakeet-CTC-1.1B`).
*   **LLM:** **TensorRT-LLM** via a local NIM container (`Llama-3-70B-Instruct`).

## 2. Implementation Steps

### Phase 1: Infrastructure & Dependencies
1.  **Update `backend/requirements.txt`**:
    *   Remove: `moviepy`, `opencv-python-headless`, `pytesseract`.
    *   Add: `nvidia-dali-cuda120`, `nemo_toolkit[asr]`, `paddlepaddle-gpu`, `paddleocr`, `ultralytics` (for export), `tensorrt`.
2.  **Update `backend/Dockerfile`**:
    *   Ensure system dependencies for DALI and NeMo are present (`libsndfile1`, etc.).
    *   Optimize pip install to prevent torch version conflicts (GB10 image comes with optimized Torch).
3.  **Update `docker-compose.yml`**:
    *   Add `llm-service` (NVIDIA NIM placeholder) to the mesh.
    *   Configure shared memory (`shm_size: 16g`) for the worker to handle massive DALI tensors.

### Phase 2: Core Pipeline Refactoring
1.  **Refactor `backend/app/services/cv.py`**:
    *   Replace `extract_frames` (OpenCV) with a `DALI` pipeline using `ops.readers.Video` and `ops.decoders.Video`.
    *   Implement `detect_ui_elements` using a TensorRT engine exported from YOLO-World.
    *   Replace `perform_ocr` (Tesseract) with `PaddleOCR`.
2.  **Refactor `backend/app/services/asr.py`**:
    *   Replace `FasterWhisper` logic with `nemo_toolkit.asr.models.ASRModel`.
    *   Load `nvidia/parakeet-ctc-1.1b` from NGC.

### Phase 3: Logic & Integration
1.  **Refactor `backend/app/services/llm.py`**:
    *   Update `OpenAI` client initialization to point to the local `llm-service` (NIM) base URL.
    *   Ensure prompt handling works with Llama-3 chat template.
2.  **Refactor `backend/app/services/video_clip.py`**:
    *   Update clip extraction to use `ffmpeg` with `-c:v h264_nvenc` for hardware-accelerated encoding of output clips.

## 3. Execution Order (Plan)
1.  **Infrastructure**: Update `requirements.txt` and `Dockerfile`.
2.  **Orchestration**: Update `docker-compose.yml` to support the new stack.
3.  **Code (CV)**: Rewrite `cv.py` for DALI/Paddle/TRT.
4.  **Code (ASR)**: Rewrite `asr.py` for NeMo.
5.  **Code (LLM)**: Update `llm.py` logic.

## 4. Verification
*   **Build Check**: Verify container builds without conflict.
*   **Runtime Check**: Since the agent cannot access a physical GB10, the code will be logically correct based on NVIDIA documentation but requires the user to execute `docker compose up --build` on the target machine.
