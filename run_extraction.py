import sys
import os

# Set up arguments
sys.argv = ['tile_extractor.py', 'C:\\Users\\somya\\Downloads\\my_folder\\catalogue.pdf', '-o', 'C:\\Users\\somya\\Downloads\\my_folder\\extracted_tiles']

print("Starting tile extraction...")
print(f"Arguments: {sys.argv}")

try:
    from tile_extractor import TileCatalogueExtractor
    from pathlib import Path
    
    pdf_file = 'C:\\Users\\somya\\Downloads\\my_folder\\catalogue.pdf'
    output_dir = 'C:\\Users\\somya\\Downloads\\my_folder\\extracted_tiles'
    
    print(f"PDF exists: {os.path.exists(pdf_file)}")
    print(f"Creating extractor...")
    
    extractor = TileCatalogueExtractor(pdf_file, output_dir)
    print(f"Running extraction...")
    extractor.extract()
    print("Extraction completed!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
