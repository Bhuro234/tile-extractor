import fitz
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io
import os

def test():
    try:
        ocr_model = PaddleOCR(use_angle_cls=False, lang='en')
        pdf_path = 'jobs/9fc8d7f0-38d2-4898-928e-4f896ad03742/Duragres-Rockstone.pdf'
        doc = fitz.open(pdf_path)
        
        # Test page 0
        pno = 0
        page = doc[pno]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        img_np = np.array(img)
        
        result = ocr_model.ocr(img_np, cls=False)
        print(f"Result for page {pno}: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
