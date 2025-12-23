import os
import cv2
import numpy as np
import torch
from PIL import Image

# GB10 Optimization Libraries: STRICT
from nvidia.dali import pipeline_def, fn
from nvidia.dali.plugin.pytorch import DALIGenericIterator
import nvidia.dali.types as types

import easyocr
from ultralytics import YOLO

# FIX: PyTorch 2.6+ defaults weights_only=True, which breaks YOLO-World loading.
# We trust the model file here, so we disable strict loading.
_original_torch_load = torch.load
def _safe_load_wrapper(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _safe_load_wrapper

# Ephemeral Model Management
import gc

class CVSession:
    def __init__(self, use_yolo=True, use_ocr=True):
        self.use_yolo = use_yolo
        self.use_ocr = use_ocr
        self.yolo = None
        self.ocr = None

    def __enter__(self):
        # Load YOLO
        if self.use_yolo:
            print("Loading YOLO-World (Ephemeral)...")
            self.yolo = YOLO('yolov8x-world.pt')
            if torch.cuda.is_available():
                self.yolo.to('cuda')
        
        # Load OCR
        if self.use_ocr:
            print("Loading EasyOCR (Ephemeral)...")
            # gpu=True/False depends on need. True is faster but VRAM heavy.
            self.ocr = easyocr.Reader(['en'], gpu=True)
            
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Unloading CV Models...")
        if self.yolo:
            del self.yolo
        if self.ocr:
            del self.ocr
        
        self.yolo = None
        self.ocr = None
        
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()




# --- DALI PIPELINE ---
@pipeline_def
def video_pipe(video_path, sequence_length=1, step=30):
    videos = fn.readers.video(
        device="gpu",
        filenames=[video_path],
        sequence_length=sequence_length,
        step=step,
        normalized=False,
        random_shuffle=False,
        image_type=types.RGB,
        name="Reader", # CRITICAL: Naming required for Iter metadata access
        skip_vfr_check=True, # Allow VFR videos
        file_list_include_preceding_frame=True
    )
    return videos

def extract_frames_dali(video_path: str, interval_seconds: int = 2):
    """
    Extract frames using DALI (NVDEC Hardware Decoding).
    STRICT: No CPU Fallback.
    """
    # Probe FPS first (using fast OpenCV probe or DALI probe)
    # DALI requires we know the step size in frames.
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    
    step_frames = int(fps * interval_seconds)
    
    try:
        # Build strict GPU pipeline
        # GB10 has 1 NVDEC. Keep batch=1 to minimize latency/complexity, 
        # but utilize full 128GB for ASR/LLM buffers.
        pipe = video_pipe(batch_size=1, num_threads=4, device_id=0, 
                          video_path=video_path, sequence_length=1, step=step_frames)
        pipe.build()
        
        # DALIGenericIterator requires the reader_name to expose metadata
        dali_iter = DALIGenericIterator(pipe, ['frames'], reader_name='Reader')
        
        frames = []
        current_time = 0.0
        
        for fast_batch in dali_iter:
            # Batch shape: [BatchSize, SeqLen, H, W, C] -> [1, 1, H, W, 3]
            gpu_tensor = fast_batch[0]['frames'] 
            
            # Transfer to CPU for CV/OCR (YOLO/EasyOCR expect CPU/GPU tensors differently)
            # YOLO/EasyOCR often handle numpy/PIL better for integration flexibility
            # Optim: Keep on GPU if models support DLPack, but for now safe copy
            frame_np = gpu_tensor.squeeze().cpu().numpy() 
            
            pil_img = Image.fromarray(frame_np)
            frames.append((current_time, pil_img))
            
            current_time += interval_seconds
        
        return frames
    except Exception as e:
        print(f"CRITICAL: DALI HW Decoding Failed: {e}")
        # FAIL JOB - No Fallback Allowed
        raise e

def detect_ui_elements(image: Image, model=None):
    """
    Open Vocabulary Detection using YOLO-World.
    """
    if model is None:
        # Fallback (Slow)
        with CVSession(use_ocr=False) as session:
            model = session.yolo
            return _run_yolo(image, model)
    else:
        return _run_yolo(image, model)

def _run_yolo(image, model):
    # Updated for Utility Pole Inspection
    model.set_classes(["utility pole", "cross arm", "transformer", "insulator", "wire", "decay", "license plate", "person", "safety cone"])
    results = model.predict(image, conf=0.15, verbose=False, device='cuda')
    
    detected = []
    for result in results:
        for box in result.boxes:
            coords = box.xyxy[0].tolist()
            cls_id = int(box.cls[0])
            label = result.names[cls_id]
            conf = float(box.conf[0])
            
            detected.append({
                "label": label,
                "box": coords,
                "confidence": conf,
                "text": label
            })
    return detected

def perform_ocr(image: Image, reader=None):
    """
    Extract text using EasyOCR (GPU).
    """
    if reader is None:
        with CVSession(use_yolo=False) as session:
            reader = session.ocr
            return _run_ocr(image, reader)
    else:
        return _run_ocr(image, reader)

def _run_ocr(image, reader):
    img_np = np.array(image)
    
    # helper for EasyOCR
    result = reader.readtext(img_np)
    
    full_text = ""
    details = {"text": [], "box": [], "conf": []}
    
    for (bbox, text, prob) in result:
        # bbox is list of 4 points [[x,y], [x,y]...]
        full_text += text + " "
        details["text"].append(text)
        details["box"].append(bbox)
        details["conf"].append(prob)
            
    return {"full_text": full_text.strip(), "details": details}

def extract_text_from_image(image: Image, reader=None) -> str:
    """
    Lightweight wrapper for text extraction.
    """
    res = perform_ocr(image, reader)
    return res["full_text"]

def process_cv(video_path: str):
    """
    Full Pipeline: DALI -> EasyOCR -> YOLO-World
    """
    frames = extract_frames_dali(video_path, interval_seconds=2)
    results = []
    
    with CVSession() as session:
        for ts, frame in frames:
            ocr_result = perform_ocr(frame, reader=session.ocr)
            ui_elements = detect_ui_elements(frame, model=session.yolo)
            
            results.append({
                "timestamp": ts,
                "ocr": ocr_result,
                "ui_elements": ui_elements
            })
        
    return results

def process_ocr_sampling(video_path: str, sample_rate: int = 5) -> dict:
    """
    Process video for OCR indexing (Sampling + EasyOCR).
    Runs in its own CVSession (Ephemeral).
    """
    import cv2
    from PIL import Image
    
    print(f"Starting OCR Sampling (rate={sample_rate}s) for {video_path}...")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Robustness Checks
    if fps <= 0:
        print(f"WARNING: Invalid FPS {fps}. Defaulting to 30.0")
        fps = 30.0
        
    duration = total_frames / fps
    ocr_texts = []
    ocr_json_data = []
    
    # Safety: frame_interval >= 1
    frame_interval = max(1, int(fps * sample_rate))
    current_frame = 0
    
    with CVSession(use_yolo=False, use_ocr=True) as session:
        while current_frame < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            ret, frame = cap.read()
            if ret:
                pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                text = extract_text_from_image(pil_img, reader=session.ocr)
                
                if text.strip():
                    timestamp = current_frame / fps
                    ocr_texts.append(f"[{timestamp:.1f}s]: {text.strip()}")
                    ocr_json_data.append({
                        "timestamp": float(f"{timestamp:.2f}"),
                        "text": text.strip()
                    })
            current_frame += frame_interval
            
    cap.release()
    print(f"OCR Sampling Complete. Found {len(ocr_texts)} text segments.")
    
    return {
        "full_text": "\n".join(ocr_texts),
        "json_data": ocr_json_data,
        "duration": duration
    }

def redact_pii(image: Image) -> Image:
    """
    PII Redaction using EasyOCR results.
    """
    import re
    from PIL import ImageDraw, ImageFilter
    
    data = perform_ocr(image)["details"]
    
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    phone_pattern = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
    
    for i, text in enumerate(data['text']):
         if email_pattern.search(text) or phone_pattern.search(text):
             # EasyOCR returns poly points
             poly = data['box'][i]
             xs = [p[0] for p in poly]
             ys = [p[1] for p in poly]
             x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
             
             box = (x1, y1, x2, y2)
             region = image.crop(box)
             blurred = region.filter(ImageFilter.GaussianBlur(radius=10))
             image.paste(blurred, box)
             
    return image

def detect_error_state(ocr_text: str, db_session = None) -> dict:
    ocr_lower = ocr_text.lower()
    # Updated for Field Inspection Issues (Decay, Damage, Safety)
    error_keywords = ["decay", "rot", "crack", "damage", "corrosion", "splinter", "danger", "warning", "unsafe", "broken"]
    
    if db_session:
        from ..models.models import GlossaryEntry
        try:
            entries = db_session.query(GlossaryEntry).all()
            for e in entries:
                if e.error_keyword and e.error_keyword.lower() not in error_keywords:
                    error_keywords.append(e.error_keyword.lower())
        except: pass

    found = [kw for kw in error_keywords if kw in ocr_lower]
    
    if found:
        return {"has_error": True, "details": f"Keywords: {found}", "resolution": suggest_resolution(found)}
    return {"has_error": False}

def suggest_resolution(keywords):
    return "Check logs."
