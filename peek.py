import fitz
import json

doc = fitz.open("C:/Users/somya/Downloads/my_folder/catalogue.pdf")
print(f"Total pages: {len(doc)}")
results = []
for pno in range(min(10, len(doc))):
    page = doc[pno]
    text = page.get_text("text").strip()
    blocks = page.get_text("dict")["blocks"]
    spans = []
    for b in blocks:
        if b.get("type") == 0:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if t:
                        spans.append({"t": t, "sz": round(span["size"],1), "bold": bool(span["flags"] & 16)})
    results.append({"page": pno+1, "raw": text[:600], "spans": spans[:25]})
doc.close()

with open("page_sample.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("Saved page_sample.json")
