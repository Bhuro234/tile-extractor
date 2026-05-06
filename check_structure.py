import fitz
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io

def test():
    try:
        ocr = PaddleOCR(use_textline_orientation=False, lang='en', enable_mkldnn=False)
        pdf_path = 'jobs/7da61030-f417-482b-8910-f782a43714af/Duragres-Rockstone.pdf'
        doc = fitz.open(pdf_path)
        page = doc[0]
        # Use 1x zoom for faster testing
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        img_np = np.array(img)
        
        result = ocr.ocr(img_np)
        print(f"Type of result: {type(result)}")
        print(f"Length of result: {len(result)}")
        print(f"Type of result[0]: {type(result[0])}")
        print(f"Keys in result[0]: {result[0].keys() if isinstance(result[0], dict) else 'N/A'}")
        
        # Print a small sample of the first detection if list
        if isinstance(result[0], list) and len(result[0]) > 0:
            print(f"Sample detection: {result[0][0]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
