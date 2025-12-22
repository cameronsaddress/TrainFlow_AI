import os
from .cv import redact_pii
import numpy as np
from PIL import Image

import subprocess
import shutil

import subprocess
import shutil

def extract_clip(video_path: str, start_ts: float, end_ts: float, output_path: str, apply_redaction: bool = True, overlay_text: str = None, enable_flash: bool = False):
    """
    Extract a subclip with optional text overlay and flash transition.
    GB10 Optimization: Uses h264_nvenc for hardware encoding via direct FFmpeg pipe.
    Strictly removes MoviePy dependency.
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Enterprise Grade: Robust Metadata Probe using ffprobe subprocess
        import json
        try:
            cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', 
                '-show_streams', 
                video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            probe = json.loads(result.stdout)
            
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            real_duration = float(video_stream['duration']) if video_stream and 'duration' in video_stream else float(probe['format']['duration'])
            width = int(video_stream['width'])
            height = int(video_stream['height'])
        except Exception as probe_e:
            print(f"Probe failed: {probe_e}. Proceeding without clamp (unsafe).")
            real_duration = 999999.0
            width, height = 1920, 1080 # Default fallback

        # Enterprise Grade: Strict Clamping
        if start_ts >= real_duration:
            print(f"Skipping clip: Start {start_ts} >= Duration {real_duration}")
            return None
        
        if end_ts > real_duration:
            print(f"Clamping clip end {end_ts} -> {real_duration}")
            end_ts = real_duration
            
        if (end_ts - start_ts) < 0.1:
            print("Clip too short.")
            return None
            
        duration = end_ts - start_ts

        if apply_redaction:
            print(f"Extracting redacted clip {start_ts}-{end_ts} (NVENC Pipe)...")
            
            # 1. Start Decoder Process (Read segment -> Raw RGB Pipe)
            decode_cmd = [
                'ffmpeg',
                '-ss', str(start_ts),
                '-t', str(duration),
                '-i', video_path,
                '-f', 'image2pipe',
                '-pix_fmt', 'rgb24',
                '-vcodec', 'rawvideo',
                '-r', '30', # Strict Sync: Force output to match Encoder's expectation
                '-'
            ]
            
            # Filter Configuration
            # Chain: [in] -> [fade] -> [text] -> [out]
            filters = []
            
            # 1. Flash Transition (Fade In White 0.2s)
            if enable_flash:
                 # fade=in:st=0:d=0.2:color=white
                 # Note: rawvideo input from pipe doesn't have stream labels like [0:v], 
                 # but since we are using -vf on the Encoder side which takes '-' (stdin) as input, it acts as [in].
                 filters.append("fade=t=in:st=0:d=0.2:color=white")
            
            # 2. Text Overlay
            if overlay_text:
                import textwrap
                # Wrap text to 40 characters
                wrapped_text = textwrap.fill(overlay_text, width=40)
                
                # Escape text for FFmpeg
                safe_text = wrapped_text.replace('\\', '\\\\\\\\').replace("'", "'\\\\\\''").replace(":", "\\\\:")
                
                # drawtext filter
                draw_filter = f"drawtext=text='{safe_text}':x=(w-text_w)/2:y=h-(text_h)-50:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=5:line_spacing=5"
                filters.append(draw_filter)
            
            # Compose Filter Chain
            if filters:
                 filter_complex = ",".join(filters)
            else:
                 filter_complex = "null"

            # 2. Start Encoder Process (Read Raw RGB Pipe -> Encode NVENC -> File)
            # CRITICAL FIX: Add audio input from original file
            encode_cmd = [
                'ffmpeg',
                '-y', # Overwrite
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-s', f'{width}x{height}',
                '-pix_fmt', 'rgb24',
                '-r', '30', # Assume 30fps for simplified pipe
                '-i', '-', # Input 0: Raw Video from Pipe
                
                # Input 1: Audio from Original File
                '-ss', str(start_ts),
                '-t', str(duration),
                '-i', video_path, 
                
                # Apply Filter if text exists
                '-vf', filter_complex,
                
                '-map', '0:v', # Map Video from Input 0 (Pipe)
                '-map', '1:a', # Map Audio from Input 1 (File)
                
                '-c:v', 'h264_nvenc', # Strict Hardware Encoding
                '-pix_fmt', 'yuv420p', # Force standard pixel format
                '-preset', 'p4',
                '-cq', '26',
                '-c:a', 'aac', 
                output_path
            ]
            
            # ... (Existing Pipe Logic matches) ...
            
            # Increase buffer size to 10MB to prevent pipe blocking on large frames
            BUFSIZE = 10 * 1024 * 1024 
            
            decoder = subprocess.Popen(decode_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=BUFSIZE)
            encoder = subprocess.Popen(encode_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=BUFSIZE)
            
            import numpy as np
            from .cv import redact_pii
            from PIL import Image

            frame_size = width * height * 3
            
            while True:
                raw_frame = decoder.stdout.read(frame_size)
                if not raw_frame or len(raw_frame) != frame_size:
                    break
                
                # Process Frame
                frame_np = np.frombuffer(raw_frame, dtype='uint8').reshape((height, width, 3))
                pil_img = Image.fromarray(frame_np)
                clean_img = redact_pii(pil_img)
                
                # Write to Encoder
                encoder.stdin.write(np.array(clean_img).tobytes())
                
            decoder.stdout.close()
            decoder.wait()
            encoder.stdin.close()
            encoder.wait()
            
            if encoder.returncode != 0:
                 print(f"Encoder failed: {encoder.stderr.read()}")
                 return None

        else:
            # Fast pass-through cut (NVENC if re-encode needed)
            # Must re-encode if overlay is requested
            if overlay_text:
                 safe_text = overlay_text.replace('\\', '\\\\\\\\').replace("'", "'\\\\\\''").replace(":", "\\\\:")
                 if len(safe_text) > 40:
                    safe_text = safe_text[:37] + "..."
                 
                 cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(start_ts),
                    '-t', str(duration),
                    '-i', video_path,
                    '-vf', f"drawtext=text='{safe_text}':x=(w-text_w)/2:y=h-80:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=5",
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p4',
                    '-c:a', 'aac',
                    output_path
                ]
            else:
                 cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(start_ts),
                    '-t', str(duration),
                    '-i', video_path,
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p4',
                    '-c:a', 'aac',
                    output_path
                ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        return output_path
    except Exception as e:
        print(f"CRITICAL: Enterprise Clipping Failed: {e}")
        # NO FALLBACK allowed per README.
        return None

def create_splash_clip(width: int, height: int, output_path: str, fps: float = 30.0):
    """
    Generate a 2-second 'TrainFlow' splash screen matching the target resolution.
    Visuals: Black BG, 'TrainFlow' (Violet), Fade In/Out.
    Audio: Silent AAC.
    """
    try:
        duration = 2.0
        
        # 1. Generate Logo Asset
        logo_path = f"/tmp/splash_logo_{width}x{height}.png"
        import subprocess
        # Assuming the tool exists in /app/app/tools/generate_logo.py
        gen_cmd = ['python3', '/app/app/tools/generate_logo.py', 
                   '--width', str(width), '--height', str(height), '--output', logo_path]
        subprocess.check_call(gen_cmd)
        
        # 2. FFmpeg Generation
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r={fps}:d={duration}',
            '-loop', '1', '-t', str(duration), '-i', logo_path,
            '-f', 'lavfi', '-t', str(duration), '-i', 'anullsrc=channel_layout=mono:sample_rate=16000',
            '-filter_complex', 
            # Overlay Logo (centered) + Fade In/Out
            f"[1:v]format=rgba,fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.5}:d=0.5[logo];" \
            f"[0:v][logo]overlay=(W-w)/2:(H-h)/2:format=auto[v]",
            '-map', '[v]',
            '-map', '2:a',
            '-c:v', 'h264_nvenc', '-pix_fmt', 'yuv420p', '-preset', 'p4',
            '-c:a', 'aac', 
            '-shortest', 
            output_path
        ]
        
        print(f"Generating Splash Screen (Image Overlay): {width}x{height} @ {fps}fps")
        subprocess.check_call(cmd)
        
        # Cleanup
        if os.path.exists(logo_path):
            os.remove(logo_path)
            
        return output_path
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return output_path
    except Exception as e:
        print(f"Splash creation failed: {e}")
        return None

def generate_vtt_content(text: str, duration: float) -> str:
    """
    Generate a simple WebVTT content string for the clip.
    SRS 15: Accessibility (Captions)
    """
    import math
    
    def fmt_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:06.3f}"
        
    end_time = fmt_time(duration)
    
    vtt = "WEBVTT\n\n"
    vtt += f"00:00:00.000 --> {end_time}\n"
    vtt += f"{text}\n"
    
    return vtt
