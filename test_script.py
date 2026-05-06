import traceback
import sys

with open("test_import.txt", "w") as f:
    try:
        from paddleocr import PaddleOCR
        f.write("PaddleOCR imported successfully.\n")
    except Exception as e:
        f.write("Failed to import PaddleOCR:\n")
        f.write(traceback.format_exc())
