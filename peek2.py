import fitz

doc = fitz.open("C:/Users/somya/Downloads/my_folder/catalogue.pdf")
page = doc[2]  # Page 3 (0-indexed)

print("=== TEXT mode ===")
print(repr(page.get_text("text")[:300]))

print("\n=== WORDS mode ===")
words = page.get_text("words")
print(words[:20])

print("\n=== HTML mode (first 800 chars) ===")
html = page.get_text("html")
print(html[:800])

print("\n=== RAWDICT chars ===")
raw = page.get_text("rawdict")
for b in raw.get("blocks", [])[:3]:
    if b.get("type") == 0:
        for line in b.get("lines", [])[:3]:
            for span in line.get("spans", [])[:3]:
                print("chars:", span.get("chars", [])[:5])
                print("text:", span.get("text", ""))

print("\n=== XML (first 500 chars) ===")
print(page.get_text("xml")[:500])

doc.close()
