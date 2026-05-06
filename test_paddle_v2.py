import fitz
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io
import os

def test():
    try:
        # use_textline_orientation=False is the modern replacement for use_angle_cls
        ocr_model = PaddleOCR(use_textline_orientation=False, lang='en')
        pdf_path = 'jobs/7da61030-f417-482b-8910-f782a43714af/Duragres-Rockstone.pdf'
        doc = fitz.open(pdf_path)
        
        # Test page 0
        pno = 0
        page = doc[pno]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        img_np = np.array(img)
        
        # Call ocr without cls argument
        result = ocr_model.ocr(img_np)
        print(f"Result for page {pno}: {result}")
        
        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                print(f"Extracted: {text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
