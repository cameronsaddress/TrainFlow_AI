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

# Global model instances
_yolo_model = None
_ocr_reader = None

def get_yolo_model():
    """
    Load YOLO-World model. (Enterprise Grade)
    """
    global _yolo_model
    if _yolo_model is None:
        print("Loading YOLO-World (GB10 Optimized)...")
        # Standard loading (Version pinned to 8.1.0 in requirements)
        _yolo_model = YOLO('yolov8x-world.pt') 
        if torch.cuda.is_available():
            _yolo_model.to('cuda')
    return _yolo_model

def get_ocr_reader():
    """
    Load EasyOCR with GPU support.
    """
    global _ocr_reader
    if _ocr_reader is None:
        print("Loading EasyOCR (GPU)...")
        _ocr_reader = easyocr.Reader(['en'], gpu=True)
    return _ocr_reader

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

def detect_ui_elements(image: Image):
    """
    Open Vocabulary Detection using YOLO-World.
    """
    model = get_yolo_model()
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

def perform_ocr(image: Image):
    """
    Extract text using EasyOCR (GPU).
    """
    reader = get_ocr_reader()
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

def process_cv(video_path: str):
    """
    Full Pipeline: DALI -> EasyOCR -> YOLO-World
    """
    frames = extract_frames_dali(video_path, interval_seconds=2)
    results = []
    
    for ts, frame in frames:
        ocr_result = perform_ocr(frame)
        ui_elements = detect_ui_elements(frame)
        
        results.append({
            "timestamp": ts,
            "ocr": ocr_result,
            "ui_elements": ui_elements
        })
        
    return results

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
