from PIL import Image, ImageDraw
import io
import os
from utils.image_processing import process_pattern_image

def test_pipeline():
    print("Creating dummy image...")
    # Create a 400x400 image
    img = Image.new("RGB", (400, 400), color=(200, 200, 200))
    # Draw a gold rectangle (fake jewellery)
    draw = ImageDraw.Draw(img)
    draw.rectangle([150, 150, 250, 250], fill=(212, 175, 55)) # Gold color
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    input_bytes = img_bytes.getvalue()
    
    print("Running process_pattern_image...")
    try:
        output_bytes = process_pattern_image(input_bytes)
        print("Success! Processed image size:", len(output_bytes))
        if len(output_bytes) > 0:
            print("Pipeline executed without fatal errors.")
    except Exception as e:
        print("Error during execution:", e)

if __name__ == "__main__":
    test_pipeline()
