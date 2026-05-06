import fitz
import pytesseract
from PIL import Image
import io, re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

doc = fitz.open("C:/Users/somya/Downloads/my_folder/catalogue.pdf")
pno = 5 # Let's try page 6
page = doc[pno]

# 1. Get image info (positions)
img_infos = page.get_image_info()
print(f"Page {pno+1} has {len(img_infos)} images.")

# 2. Render page for OCR
mat = fitz.Matrix(2, 2)
pix = page.get_pixmap(matrix=mat)
img = Image.open(io.BytesIO(pix.tobytes("png")))

# 3. Get OCR data with boxes
# Use image_to_data to get coordinates of every word
ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

# Scale OCR coords back to PDF coords (OCR was at 2x zoom)
def scale_ocr(val): return val / 2.0

words = []
for i in range(len(ocr_data['text'])):
    if ocr_data['text'][i].strip():
        words.append({
            'text': ocr_data['text'][i],
            'bbox': [
                scale_ocr(ocr_data['left'][i]),
                scale_ocr(ocr_data['top'][i]),
                scale_ocr(ocr_data['left'][i] + ocr_data['width'][i]),
                scale_ocr(ocr_data['top'][i] + ocr_data['height'][i])
            ]
        })

# 4. For each image, find nearby text
for i, info in enumerate(img_infos):
    ibox = info['bbox'] # [x0, y0, x1, y1]
    print(f"\nImage {i} at {ibox}:")
    
    # Look for text in a 100pt buffer above/below/left
    search_box = [ibox[0] - 50, ibox[1] - 100, ibox[2] + 50, ibox[3] + 100]
    
    nearby_text = []
    for w in words:
        wbox = w['bbox']
        # Check if word is inside or very close to the image
        if (wbox[0] >= search_box[0] and wbox[2] <= search_box[2] and
            wbox[1] >= search_box[1] and wbox[3] <= search_box[3]):
            nearby_text.append(w['text'])
    
    full_text = " ".join(nearby_text)
    print(f"  Detected Text nearby: {full_text[:200]}...")

doc.close()
