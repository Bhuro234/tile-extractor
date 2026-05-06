import numpy as np
from paddleocr import PaddleOCR
import time

def test():
    try:
        print("Initializing PaddleOCR...")
        ocr = PaddleOCR(use_textline_orientation=False, lang='en', enable_mkldnn=False)
        print("Creating tiny image...")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        print("Running OCR...")
        start = time.time()
        result = ocr.ocr(img)
        end = time.time()
        print(f"OCR finished in {end-start:.2f} seconds.")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
