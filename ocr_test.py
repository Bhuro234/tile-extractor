import fitz
from PIL import Image
import pytesseract
import io, re

# Path to tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

doc = fitz.open("C:/Users/somya/Downloads/my_folder/catalogue.pdf")

for pno in range(min(6, len(doc))):
    page = doc[pno]
    # Render at 2x zoom for better OCR accuracy
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    
    # OCR full page
    text = pytesseract.image_to_string(img)
    
    if text.strip():
        print(f"\n{'='*50}")
        print(f"PAGE {pno+1}:")
        print(text[:600])

doc.close()
