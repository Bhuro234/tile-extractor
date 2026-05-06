#!/usr/bin/env python3
try:
    print("Starting import test...")
    import tile_extractor
    print("Import successful!")
except Exception as e:
    print(f"Error during import: {e}")
    import traceback
    traceback.print_exc()
