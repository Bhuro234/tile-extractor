#!/usr/bin/env python3
"""
Debug script to see what text is being extracted from PDF
"""

import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("PyMuPDF not installed")

from tile_extractor import PageMetadataExtractor

def debug_page(pdf_path, page_num=0):
    doc = fitz.open(pdf_path)
    
    if page_num >= len(doc):
        print(f"PDF has only {len(doc)} pages")
        return
    
    print(f"\n{'='*60}")
    print(f"DEBUG: Page {page_num + 1}")
    print(f"{'='*60}\n")
    
    # 1. Show ALL raw text from page
    page = doc[page_num]
    raw_text = page.get_text()
    print("RAW TEXT FROM PAGE:")
    print("-" * 60)
    print(raw_text)
    print("\n")
    
    # 2. Show extracted words with coordinates
    print("EXTRACTED WORDS (with positions):")
    print("-" * 60)
    words = page.get_text("words")
    for i, w in enumerate(words[:30]):  # First 30 words
        print(f"{i+1:2d}. '{w[4]}' at ({w[0]:.0f}, {w[1]:.0f})")
    if len(words) > 30:
        print(f"... and {len(words) - 30} more words")
    print("\n")
    
    # 3. Show what metadata extractor finds
    print("EXTRACTED METADATA:")
    print("-" * 60)
    extractor = PageMetadataExtractor()
    meta = extractor.extract_page_meta(doc, page_num)
    
    products = meta.get("products", [])
    if not products:
        print("❌ NO PRODUCTS FOUND!")
        print("\nTIP: Check the raw text above for:")
        print("  - Product names (mostly UPPERCASE)")
        print("  - Sizes (e.g., 300x600mm, 600x1200cm)")
        print("  - Surfaces (polished, matte, glossy, etc.)")
        print("  - Wall/Floor indicators")
    else:
        for i, p in enumerate(products, 1):
            print(f"\nProduct {i}:")
            print(f"  Name:    {p.get('name', '-')}")
            print(f"  Size:    {p.get('size', '-')}")
            print(f"  Surface: {p.get('surface', '-')}")
            print(f"  Wall:    {p.get('wall', '-')}")
    
    doc.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_extract.py <pdf_path> [page_number]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
    
    if not Path(pdf_path).exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)
    
    debug_page(pdf_path, page_num)
