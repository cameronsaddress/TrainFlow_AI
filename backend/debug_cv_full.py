import sys
import os
sys.path.append(os.getcwd())
print("Starting Debug Script Level 2...", flush=True)

try:
    from app.services import cv
    print("CV Service Imported.", flush=True)
except Exception as e:
    print(f"Failed to import CV: {e}", flush=True)
    sys.exit(1)

import cv2
video_path = "/app/data/corpus/8d74415f-bdad-44f7-bef9-4bf8ac4e330f.mp4"

print("Instantiating CVSession (Loading Models)...", flush=True)
try:
    with cv.CVSession(use_yolo=False, use_ocr=True) as session:
        print("CVSession Created. Models Loaded.", flush=True)
        
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            from PIL import Image
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            print("Performing OCR on one frame...", flush=True)
            result = cv.extract_text_from_image(pil_img, reader=session.ocr)
            print(f"OCR Result: {result[:50]}...", flush=True)
        cap.release()
except Exception as e:
    print(f"CVSession Failed: {e}", flush=True)

print("Debug Level 2 Complete.", flush=True)
