#!/usr/bin/env python3
import sys
print("Script started", flush=True)

try:
    from tile_extractor import TileCatalogueExtractor
    print("Import successful", flush=True)
    
    pdf_path = r"C:\Users\somya\Downloads\my_folder\catalogue.pdf"
    output_dir = r"C:\Users\somya\Downloads\my_folder\test_output"
    
    print(f"PDF: {pdf_path}", flush=True)
    print(f"Output: {output_dir}", flush=True)
    
    extractor = TileCatalogueExtractor(pdf_path, output_dir, verbose=True)
    print("Extractor created", flush=True)
    
    extractor.extract()
    print("Extraction completed", flush=True)
    
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
