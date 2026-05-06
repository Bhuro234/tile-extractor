#!/usr/bin/env python3
import fitz
from pathlib import Path

pdf_path = r"C:\Users\somya\Downloads\my_folder\catalogue.pdf"

print(f"Checking: {pdf_path}")
print(f"Exists: {Path(pdf_path).exists()}")

try:
    doc = fitz.open(pdf_path)
    print(f"✓ PDF opened successfully")
    print(f"Total pages: {len(doc)}")
    
    page = doc[0]
    images = page.get_images()
    print(f"Page 1 has {len(images)} images")
    
    # Try to extract first image
    if images:
        xref = images[0][0]
        img_data = doc.extract_image(xref)
        print(f"First image: {img_data['ext']} ({len(img_data['image'])} bytes)")
        print(f"✓ Can extract images")
    
    doc.close()
    print("\n✓ PDF is readable and contains image data")
    
except Exception as e:
    print(f"✗ Error: {e}")
