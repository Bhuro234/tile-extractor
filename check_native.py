import fitz
try:
    doc = fitz.open('jobs/7da61030-f417-482b-8910-f782a43714af/Duragres-Rockstone.pdf')
    page = doc[0]
    text = page.get_text("text").strip()
    words = page.get_text("words")
    print(f"Native Text length: {len(text)}")
    print(f"Native Words count: {len(words)}")
except Exception as e:
    print(f"Error: {e}")
