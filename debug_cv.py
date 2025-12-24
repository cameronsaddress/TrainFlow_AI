import sys
import os
sys.path.append(os.getcwd())
print("Starting Debug Script...", flush=True)

try:
    from app.services import cv
    print("CV Service Imported Successfully.", flush=True)
except Exception as e:
    print(f"Failed to import CV: {e}", flush=True)
    sys.exit(1)

import cv2
video_path = "/app/data/corpus/8d74415f-bdad-44f7-bef9-4bf8ac4e330f.mp4"

print(f"Attempting to open video: {video_path}", flush=True)
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.", flush=True)
else:
    print("Video Opened!", flush=True)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    print(f"FPS: {fps}, Total Frames: {frames}", flush=True)
    
    # Try reading one frame
    ret, frame = cap.read()
    print(f"Read Match Frame: {ret}", flush=True)

print("Debug Complete.", flush=True)
