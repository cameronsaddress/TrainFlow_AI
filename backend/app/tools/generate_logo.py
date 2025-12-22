from PIL import Image, ImageDraw, ImageFont, ImageColor
import os

def create_logo(output_path, text="TrainFlow", width=640, height=360):
    # Colors
    bg_color = (0, 0, 0) # Black for seamless fade
    text_color_start = (96, 165, 250) # Blue-400
    text_color_end = (167, 139, 250) # Violet-400
    
    # Create Image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Font (Use a default sans-serif if custom not available, or try to load one)
    try:
        # Try to load a known font on Linux (DejaVuSans)
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
        font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw Icon (Box)
    # Center X = width/2
    # Icon is 60x60
    # Text is approx 300 wide.
    # Total width approx 380.
    start_x = (width - 380) // 2
    icon_y = (height - 60) // 2
    
    # Icon with gradient-ish fill (Solid Blue-400 for simplicity)
    draw.rectangle([start_x, icon_y, start_x + 60, icon_y + 60], fill=text_color_start, outline=None)
    
    # Text with Violet-400
    text_x = start_x + 80
    text_y = (height - 60) // 2 # Approximate centering
    draw.text((text_x, text_y), text, font=font, fill=text_color_end)
    
    # "AI" Tag
    draw.text((text_x + 320, text_y), "AI", font=font, fill=text_color_start)

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"Generated logo at {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--output", type=str, default="/app/assets/splash_logo.png")
    args = parser.parse_args()
    
    create_logo(args.output, width=args.width, height=args.height)
