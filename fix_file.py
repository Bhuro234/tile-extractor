#!/usr/bin/env python3
import re

# Read the corrupted file
with open('tile_extractor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the literal \n with actual newlines in the _extract_text_from_image method
content = content.replace('def _extract_text_from_image(self, img_bytes):\\n', 'def _extract_text_from_image(self, img_bytes):\n')

# Find and fix all other \n in that method
lines = content.split('\n')
fixed_lines = []
in_method = False

for i, line in enumerate(lines):
    if 'def _extract_text_from_image' in line:
        in_method = True
    elif in_method and line.strip().startswith('def '):
        in_method = False
    
    # Replace escaped newlines with actual newlines within the method
    if in_method and '\\n' in line:
        # This line has escaped newlines - split it
        parts = line.split('\\n')
        for j, part in enumerate(parts):
            if j > 0:
                fixed_lines.append(part)
            else:
                fixed_lines.append(line)
    else:
        fixed_lines.append(line)

# Write back
with open('tile_extractor.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))

print("File fixed!")
