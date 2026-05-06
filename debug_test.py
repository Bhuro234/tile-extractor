#!/usr/bin/env python3
import sys
sys.stdout.flush()
print("TEST 1: Module starting", flush=True)

try:
    import fitz
    print("TEST 2: fitz imported", flush=True)
    
    doc = fitz.open("C:\\Users\\somya\\Downloads\\my_folder\\catalogue.pdf")
    print(f"TEST 3: PDF opened, {len(doc)} pages", flush=True)
    
    page = doc[0]
    print("TEST 4: First page loaded", flush=True)
    
    # Test getting images
    images = page.get_image_info()
    print(f"TEST 5: Found {len(images)} images", flush=True)
    
    if images:
        info = images[0]
        print(f"TEST 6: First image info: {info}", flush=True)
        
        # Try to get the bbox
        try:
            rect = page.get_image_bbox(info['number'])
            print(f"TEST 7: Image bbox: {rect}", flush=True)
        except AttributeError as e:
            print(f"TEST 7: ERROR - get_image_bbox not available: {e}", flush=True)
            try:
                # Try alternative method
                rect = page.get_image_rects(info['xref'])[0]
                print(f"TEST 7b: Using get_image_rects: {rect}", flush=True)
            except Exception as e2:
                print(f"TEST 7b: ERROR - {e2}", flush=True)
    
    doc.close()
    print("TEST 8: Complete", flush=True)
    
except Exception as e:
    import traceback
    print(f"ERROR: {e}", flush=True)
    traceback.print_exc()
