#!/usr/bin/env python3
import fitz
pdf_path = "C:\\Users\\somya\\Downloads\\my_folder\\catalogue.pdf"
doc = fitz.open(pdf_path)

for pno in range(min(3, len(doc))):
    page = doc[pno]
    print(f"\n=== PAGE {pno + 1} ===")
    
    # Try different text extraction methods
    raw_text = page.get_text()
    print(f"Raw text length: {len(raw_text)}")
    if raw_text:
        print(f"First 500 chars: {raw_text[:500]}")
    
    # Try with blocks
    blocks = page.get_text("blocks")
    print(f"Number of blocks: {len(blocks)}")
    for i, block in enumerate(blocks[:3]):
        print(f"  Block {i}: {block[:100] if len(str(block)) > 100 else block}")

doc.close()
