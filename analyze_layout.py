import fitz

doc = fitz.open("C:/Users/somya/Downloads/my_folder/catalogue.pdf")
page = doc[17] # Page 18 as per screenshot (0-indexed 17)

print(f"Page size: {page.rect}")
img_infos = page.get_image_info()
print(f"Found {len(img_infos)} images on page 18")

for i, info in enumerate(img_infos):
    print(f"\nImage {i}:")
    print(f"  BBox: {info['bbox']}")
    print(f"  Width/Height: {info['width']}x{info['height']}")

doc.close()
