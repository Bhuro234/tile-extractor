#!/usr/bin/env python3
"""
Fix corrupted tile_extractor.py by replacing literal \n with actual newlines
"""

import os
import sys
import py_compile

def fix_corrupted_file():
    # File path
    file_path = r'C:\Users\somya\.gemini\antigravity\scratch\TileExtractor\tile_extractor.py'
    
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return False
    
    print(f"Reading file: {file_path}")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count literal backslash-n occurrences before replacement
    literal_count = content.count(r'\n')
    print(f"Found {literal_count} literal backslash-n characters")
    
    if literal_count == 0:
        print("No literal backslash-n characters found. File may already be fixed.")
        return True
    
    # Replace literal \n with actual newlines
    fixed_content = content.replace(r'\n', '\n')
    
    # Write back
    print("Writing corrected content back to file...")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print("✓ File fixed - replaced literal backslash-n with actual newlines")
    
    # Verify with py_compile
    print("\nVerifying syntax with py_compile...")
    try:
        py_compile.compile(file_path, doraise=True)
        print("✓ File compiles successfully!")
        return True
    except py_compile.PyCompileError as e:
        print(f"✗ Compilation error: {e}")
        return False

if __name__ == '__main__':
    success = fix_corrupted_file()
    sys.exit(0 if success else 1)
