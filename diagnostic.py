#!/usr/bin/env python3
"""Diagnostic tool to understand PDF text/image layout"""
import sys
try:
    import fitz
except:
    sys.exit("PyMuPDF required")

pdf_path = "C:\\Users\\somya\\Downloads\\my_folder\\catalogue.pdf"
doc = fitz.open(pdf_path)

print("=" * 80)
print("PDF LAYOUT DIAGNOSTIC")
print("=" * 80)

# Analyze first 3 pages
for pno in range(min(3, len(doc))):
    page = doc[pno]
    print(f"\n--- PAGE {pno + 1} ---\n")
    
    # Extract text blocks with coordinates
    text_dict = page.get_text("dict")
    print("TEXT BLOCKS:")
    for block in text_dict.get("blocks", []):
        if block["type"] == 0:  # Text block
            bbox = block["bbox"]
            text_content = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text_content += span.get("text", "")
            
            if text_content.strip():
                print(f"  Rect({bbox[0]:.0f}, {bbox[1]:.0f}, {bbox[2]:.0f}, {bbox[3]:.0f}): {text_content[:80]}")
    
    # Extract image info
    print("\nIMAGES:")
    for info in page.get_image_info():
        xref = info.get('xref')
        try:
            rects = page.get_image_rects(xref)
            if rects:
                rect = rects[0]
                print(f"  Rect({rect[0]:.0f}, {rect[1]:.0f}, {rect[2]:.0f}, {rect[3]:.0f}): Image xref={xref}")
        except:
            pass

doc.close()
print("\n" + "=" * 80)
