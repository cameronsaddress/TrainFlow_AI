import sys
import argparse
import json
import logging
import os

# Configure logging for the subprocess
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ServicesCLI")

def print_gpu_stats():
    import torch
    if torch.cuda.is_available():
        # STRICT LIMIT: Enforce 80% Memory Cap for this subprocess
        # This prevents the "Kernel Panic" by ensuring PyTorch never requests >80% of VRAM.
        # If it hits the limit, it raises OOM (caught by try/except) instead of freezing the OS.
        current_limit = torch.cuda.get_per_process_memory_fraction()
        if current_limit > 0.8: # Only set if not already lower
             torch.cuda.set_per_process_memory_fraction(0.8)
        
        free, total = torch.cuda.mem_get_info()
        print(f"[CLI-MEM] GPU Free: {free/1e9:.2f}GB / {total/1e9:.2f}GB | Limit: 80%", flush=True)

def run_asr(video_path, output_path):
    print_gpu_stats()
    from app.services import asr
    logger.info(f"Subprocess: Starting ASR for {video_path}")
    
    try:
        result = asr.process_asr(video_path)
        with open(output_path, 'w') as f:
            json.dump(result, f)
        logger.info("Subprocess: ASR Complete")
    except Exception as e:
        logger.error(f"Subprocess ASR Failed: {e}")
        sys.exit(1)
    finally:
        print_gpu_stats()

def run_ocr_sampling(video_path, output_path):
    print_gpu_stats()
    from app.services import cv
    logger.info(f"Subprocess: Starting OCR Sampling for {video_path}")
    
    try:
        result = cv.process_ocr_sampling(video_path)
        with open(output_path, 'w') as f:
            json.dump(result, f)
        logger.info("Subprocess: OCR Complete")
    except Exception as e:
        logger.error(f"Subprocess OCR Failed: {e}")
        sys.exit(1)
    finally:
        print_gpu_stats()

def main():
    parser = argparse.ArgumentParser(description="TrainFlow Service CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # ASR Command
    asr_parser = subparsers.add_parser("asr")
    asr_parser.add_argument("video_path")
    asr_parser.add_argument("output_path")
    
    # OCR Sampling Command
    ocr_parser = subparsers.add_parser("ocr_sampling")
    ocr_parser.add_argument("video_path")
    ocr_parser.add_argument("output_path")
    
    args = parser.parse_args()
    
    # Ensure app module is in path
    sys.path.append(os.getcwd())
    
    if args.command == "asr":
        run_asr(args.video_path, args.output_path)
    elif args.command == "ocr_sampling":
        run_ocr_sampling(args.video_path, args.output_path)

if __name__ == "__main__":
    main()
