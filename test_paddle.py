#!/usr/bin/env python3
import sys
import os

print("=" * 60)
print("Testing PaddleOCR initialization...")
print("=" * 60)

try:
    print("\n1. Importing PaddleOCR...", end=" ", flush=True)
    from paddleocr import PaddleOCR
    print("✓ OK")
    
    print("2. Initializing PaddleOCR...", end=" ", flush=True)
    print("(This may take a minute on first run)", flush=True)
    ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
    print("✓ OK\n")
    
    print("3. Testing with a simple image...", end=" ", flush=True)
    from PIL import Image, ImageDraw
    import io
    
    # Create a simple test image
    img = Image.new('RGB', (200, 100), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), "Test 300x600mm", fill='black')
    
    # Save to BytesIO
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    result = ocr.ocr(img_bytes, cls=True)
    print("✓ OK")
    
    print("\n4. OCR Result:")
    if result:
        for line in result:
            for detection in line:
                text = detection[1][0]
                conf = detection[1][1]
                print(f"   - '{text}' (confidence: {conf:.2f})")
    
    print("\n✓ PaddleOCR works perfectly!")
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
