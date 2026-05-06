import fitz
import sys

try:
    doc = fitz.open('jobs/9fc8d7f0-38d2-4898-928e-4f896ad03742/Duragres-Rockstone.pdf')
    for i in range(min(3, len(doc))):
        page = doc[i]
        words = page.get_text("words")
        text = page.get_text("text").strip()
        print(f"Page {i}: words={len(words)}, text_len={len(text)}")
except Exception as e:
    print(f"Error: {e}")
