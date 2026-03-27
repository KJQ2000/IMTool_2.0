"""
utils/image_processing.py
─────────────────────────
Enterprise Image Processing Pipeline for Jewellery Pattern Management.

Pipeline Steps:
1. Load Image.
2. Use YOLO-World (Open-Vocabulary Object Detection) to find the jewellery.
3. Crop to the detected bounding box (Zoom in).
4. Use `rembg` to remove the background (skin, hand).
5. Apply CLAHE and Unsharp Masking to enhance the jewellery details.
6. Composite onto a clean white background.
"""

from __future__ import annotations

import io
import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy loading of heavy AI models to avoid slow startup times
_yolo_model = None


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        logger.info("Loading YOLO-World model for the first time...")
        # Note: This requires ultralytics to be installed
        from ultralytics import YOLOWorld

        # Use the small world model for open vocabulary detection
        _yolo_model = YOLOWorld("model/yolov8s-world.pt")
        # Define the custom classes we are looking for
        _yolo_model.set_classes(
            [
                "jewellery",
                "ring",
                "necklace",
                "earring",
                "bracelet",
                "pendant",
                "bangle",
                "anklet",
                "gold",
            ]
        )
    return _yolo_model


def remove_background(image: Image.Image) -> Image.Image:
    """Removes the background using rembg."""
    try:
        from rembg import remove
        return remove(image)
    except ImportError:
        logger.warning("rembg is not installed. Skipping background removal.")
        return image


def enhance_jewellery_details(image_rgba: Image.Image) -> Image.Image:
    """
    Applies CLAHE (Contrast Limited Adaptive Histogram Equalization) and
    unsharp masking to the non-transparent parts of the image to make
    gold and gemstones pop.
    """
    # Convert PIL to specific OpenCV formats
    cv_img = np.array(image_rgba)
    
    if cv_img.shape[2] == 4:
        # Separate alpha channel
        bgr = cv2.cvtColor(cv_img, cv2.COLOR_RGBA2BGR)
        alpha = cv_img[:, :, 3]
    else:
        bgr = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
        alpha = np.ones(bgr.shape[:2], dtype=np.uint8) * 255

    # Convert to LAB color space for CLAHE
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # Apply CLAHE to L-channel
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)

    # Merge back and convert to BGR
    limg = cv2.merge((cl, a, b))
    enhanced_bgr = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

    # Apply Unsharp Masking
    gaussian = cv2.GaussianBlur(enhanced_bgr, (0, 0), 2.0)
    unsharp = cv2.addWeighted(enhanced_bgr, 1.5, gaussian, -0.5, 0)

    # Reattach Alpha
    if cv_img.shape[2] == 4:
        final_img = cv2.cvtColor(unsharp, cv2.COLOR_BGR2BGRA)
        final_img[:, :, 3] = alpha
        return Image.fromarray(cv2.cvtColor(final_img, cv2.COLOR_BGRA2RGBA))
    else:
        return Image.fromarray(cv2.cvtColor(unsharp, cv2.COLOR_BGR2RGB))


def composite_on_white(image_rgba: Image.Image) -> Image.Image:
    """Pastes a transparent RGBA image onto a solid white background."""
    if image_rgba.mode != "RGBA":
        return image_rgba
        
    # Create white background
    bg = Image.new("RGB", image_rgba.size, (255, 255, 255))
    # Paste using alpha channel as mask
    bg.paste(image_rgba, mask=image_rgba.split()[3])
    return bg


def process_pattern_image(image_bytes: bytes) -> bytes:
    """
    The full enterprise pipeline:
    1. YOLO-World Object Detection & Crop
    2. rembg Background Removal
    3. OpenCV Enhancement
    4. Composite on White
    """
    try:
        # Load image via PIL
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # 1. Object Detection using YOLO-World
        logger.info("Running YOLO-World object detection...")
        model = get_yolo_model()
        results = model.predict(img, conf=0.1, iou=0.45) # Lower conf to catch small rings
        
        cropped_img = img
        best_box = None
        
        if results and len(results[0].boxes) > 0:
            # Get the box with the highest confidence
            boxes = results[0].boxes
            best_conf = -1
            
            for box in boxes:
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    best_box = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                    
            if best_box:
                # Add 15% padding so we don't clip the edges of the ring tightly
                x1, y1, x2, y2 = best_box
                w = x2 - x1
                h = y2 - y1
                padding_x = w * 0.15
                padding_y = h * 0.15
                
                crop_x1 = max(0, int(x1 - padding_x))
                crop_y1 = max(0, int(y1 - padding_y))
                crop_x2 = min(img.width, int(x2 + padding_x))
                crop_y2 = min(img.height, int(y2 + padding_y))
                
                cropped_img = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                logger.info(f"Cropped to bounding box: {crop_x1},{crop_y1} to {crop_x2},{crop_y2}")

        # 2. Background Removal
        logger.info("Removing background...")
        no_bg_img = remove_background(cropped_img)
        
        # 3. Enhance Details
        logger.info("Enhancing details...")
        enhanced_img = enhance_jewellery_details(no_bg_img)
        
        # 4. Composite on White Background
        final_img = composite_on_white(enhanced_img)
        
        # Return as bytes
        out_buffer = io.BytesIO()
        final_img.save(out_buffer, format="JPEG", quality=90)
        return out_buffer.getvalue()

    except Exception as e:
        logger.error(f"Failed to process image through pipeline: {e}", exc_info=True)
        # If any step fails completely, return original bytes to avoid breaking the upload flow
        return image_bytes
