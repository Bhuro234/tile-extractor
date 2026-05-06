#!/usr/bin/env python3
"""
Tile Catalogue — Spatial Image Extractor (v4)
=============================================
Extracts tile images and matches them to nearby text metadata (Size, Surface, Name).
"""

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import re
import struct
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("PyMuPDF not installed. Run: pip install pymupdf")

try:
    from PIL import Image, ImageFilter, ImageStat
except ImportError:
    sys.exit("Pillow not installed. Run: pip install Pillow")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    import pytesseract
    # Tesseract Path Configuration
    TESS_PATH_WIN = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    TESS_PATH_LINUX = '/usr/bin/tesseract'
    
    if os.path.exists(TESS_PATH_WIN):
        pytesseract.pytesseract.tesseract_cmd = TESS_PATH_WIN
    elif os.path.exists(TESS_PATH_LINUX):
        pytesseract.pytesseract.tesseract_cmd = TESS_PATH_LINUX
    else:
        # Default fallback
        pytesseract.pytesseract.tesseract_cmd = 'tesseract'

    HAS_OCR = True
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        print("WARNING: Tesseract not found in PATH or standard location.")
        HAS_OCR = False
except ImportError:
    HAS_OCR = False


# ── Page Metadata Extractor (Spatial OCR) ──────────────────────────────────

class PageMetadataExtractor:
    """Renders PDF pages and uses spatial OCR to match text to individual tiles."""

    SIZE_RE    = re.compile(r'(\d{3,4})\s*[xXxX×]\s*[lI]?(\d{3,4})\s*(mm|cm)?', re.I)
    THICK_RE   = re.compile(r'(\d{1,2}(?:\.\d)?)\s*mm', re.I)
    FACES_RE   = re.compile(r'(\d+)\s*(?:faces?)\b', re.I)

    KNOWN_SURFACES = [
        'full polished', 'hd polished', 'full polish',
        'impression', 'matt', 'matte', 'glossy', 'gloss',
        'satin', 'natural', 'lappato', 'structured',
        'rustic', 'hd gloss', 'sugar', 'carving',
        'soft polished', 'anti-skid',
    ]

    def __init__(self):
        self._current_page_data = None
        self._current_pno = -1

    def prepare_page(self, doc, pno: int):
        if self._current_pno == pno:
            return
        
        # 1. Try PyMuPDF native text extraction FIRST (Near-instant, works for digital PDFs)
        try:
            page = doc[pno]
            raw_words = page.get_text("words") # x0, y0, x1, y1, word, block_no, line_no, word_no
            if len(raw_words) > 0: # If we found ANY text, use it
                words = []
                for w in raw_words:
                    words.append({
                        'text': w[4],
                        'bbox': [w[0], w[1], w[2], w[3]]
                    })
                self._current_page_data = words
                self._current_pno = pno
                return
        except Exception as e:
            print(f"Native extraction failed: {e}")

        # 2. Try OCR only if Native failed (For scanned/image-only PDFs)
        if HAS_OCR:
            try:
                page = doc[pno]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                words = []
                for i in range(len(data['text'])):
                    txt = data['text'][i].strip()
                    if txt:
                        words.append({
                            'text': txt,
                            'bbox': [
                                data['left'][i]/2.0, data['top'][i]/2.0,
                                (data['left'][i] + data['width'][i])/2.0,
                                (data['top'][i] + data['height'][i])/2.0
                            ]
                        })
                self._current_page_data = words
                self._current_pno = pno
                return
            except Exception as e:
                print(f"OCR failed for page {pno}: {e}")

        self._current_page_data = []
        self._current_pno = pno

    def extract_page_meta(self, doc, pno: int) -> dict:
        """Extract all unique Names, Sizes, and Surfaces from the entire page."""
        self.prepare_page(doc, pno)
        if not self._current_page_data:
            return {"products": []}
        
        all_lines = self._get_lines_with_bbox(self._current_page_data)
        
        all_names = []
        all_sizes = []
        all_surfaces = []
        
        for text, _ in all_lines:
            clean = text.strip()
            low = clean.lower()
            
            # 1. Size
            m_s = self.SIZE_RE.search(clean)
            if m_s:
                w, h, u = m_s.group(1), m_s.group(2).replace('I','1').replace('l','1'), (m_s.group(3) or 'mm')
                size_str = f"{w}x{h}{u}"
                if size_str not in all_sizes: all_sizes.append(size_str)
                continue

            # 2. Surface
            found_sf = None
            for sf in self.KNOWN_SURFACES:
                if sf in low:
                    surf = sf.title()
                    if surf not in all_surfaces: all_surfaces.append(surf)
                    break
            if found_sf: continue

            # 3. Name (Product Title)
            temp_clean = clean
            for prefix in ["Wall & Floor:", "Wall:", "Floor:", "Wall & Floor :", "Product:"]:
                if temp_clean.lower().startswith(prefix.lower()):
                    temp_clean = temp_clean[len(prefix):].strip()
                    break
            
            upper_only = "".join(c for c in temp_clean if c.isupper())
            if len(temp_clean) > 4 and len(upper_only) >= 4 and len(upper_only) / len(temp_clean) > 0.5:
                name = temp_clean.title()
                if name not in all_names: all_names.append(name)

        # 4. Also use the "Super-Greedy" Fallback on the raw text to ensure nothing is missed
        raw_text = doc[pno].get_text()
        found_sizes = self.SIZE_RE.findall(raw_text)
        for s in found_sizes:
            size_str = f"{s[0]}x{s[1]}{s[2] or 'mm'}"
            if size_str not in all_sizes: all_sizes.append(size_str)
            
        low_text = raw_text.lower()
        for sf in self.KNOWN_SURFACES:
            if sf in low_text:
                surf = sf.title()
                if surf not in all_surfaces: all_surfaces.append(surf)

        # 5. Return a single aggregated product for the page
        if all_names or all_sizes or all_surfaces:
            return {"products": [{
                "name": "<br>".join(all_names) if all_names else "-",
                "size": "<br>".join(all_sizes) if all_sizes else "-",
                "surface": "<br>".join(all_surfaces) if all_surfaces else "-"
            }]}

        return {"products": []}

    def _get_lines_with_bbox(self, words):
        if not words: return []
        words.sort(key=lambda x: (x['bbox'][1], x['bbox'][0]))
        lines = []
        curr_line = [words[0]]
        for w in words[1:]:
            if abs(w['bbox'][1] - curr_line[-1]['bbox'][1]) < 10:
                curr_line.append(w)
            else:
                text = " ".join([x['text'] for x in curr_line])
                bbox = [min(x['bbox'][0] for x in curr_line), min(x['bbox'][1] for x in curr_line),
                        max(x['bbox'][2] for x in curr_line), max(x['bbox'][3] for x in curr_line)]
                lines.append((text, bbox))
                curr_line = [w]
        text = " ".join([x['text'] for x in curr_line])
        bbox = [min(x['bbox'][0] for x in curr_line), min(x['bbox'][1] for x in curr_line),
                max(x['bbox'][2] for x in curr_line), max(x['bbox'][3] for x in curr_line)]
        lines.append((text, bbox))
        return lines



# ── Tile Filter ────────────────────────────────────────────────────────────

class TileFilter:
    def should_reject(self, img) -> str:
        w, h = img.size
        short = min(w, h)
        if short < 80: return "too small"
        aspect = w / h
        if aspect < 0.18 or aspect > 5.5: return "aspect ratio"
        
        thumb = img.copy()
        thumb.thumbnail((128, 128), Image.BOX)
        rgb = thumb.convert("RGB")
        stat = ImageStat.Stat(rgb)
        std = sum(stat.stddev[:3])/3
        bright = sum(stat.mean[:3])/3

        if short >= 150:
            if std < 1.5 and bright > 180: return "blank"
            edges = rgb.convert("L").filter(ImageFilter.FIND_EDGES)
            if ImageStat.Stat(edges).mean[0] > 75: return "QR/logo"
        else:
            if std > 100: return "QR code"
            if aspect > 2.5: return "logo"
        return ""


# ── Processing Helpers ─────────────────────────────────────────────────────

def prepare_output(data, ext):
    try:
        img = Image.open(io.BytesIO(data))
        has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
        mode = "RGBA" if has_alpha else "RGB"
        if img.mode != mode: img = img.convert(mode)
        buf = io.BytesIO()
        if mode == "RGBA" or ext == "png":
            img.save(buf, format="PNG", optimize=False, compress_level=1)
            return buf.getvalue(), "png"
        else:
            img.save(buf, format="JPEG", quality=92)
            return buf.getvalue(), "jpg"
    except Exception:
        return None, ""


# ── Extractor ──────────────────────────────────────────────────────────────

class TileCatalogueExtractor:
    def __init__(self, pdf_path: str, output_dir: str, verbose: bool = False):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.tile_filter = TileFilter()
        self.meta_extractor = PageMetadataExtractor()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seen_hashes = set()
        self.stats = {"pages":0,"raw_found":0,"tiles_saved":0,"skipped_dup":0,"skipped_filter":0,"errors":0}
        self._reject_log = {}
        self._csv_rows = []
        self._page_meta = {}

    def extract_images(self, pages=None, progress_callback=None):
        doc = fitz.open(self.pdf_path)
        total = len(doc)
        self.stats["pages"] = total
        plist = pages if pages is not None else list(range(total))

        tasks = []
        for pno in plist:
            page = doc[pno]
            for info in page.get_image_info():
                tasks.append((pno, info))

        self.stats["raw_found"] = len(tasks)
        print("  Extracting images...")
        
        it = tqdm(tasks) if HAS_TQDM else tasks
        for i, (pno, info) in enumerate(it):
            self._process_spatial(doc, pno, info)
            if progress_callback:
                progress_callback(int((i + 1) / len(tasks) * 100), 100)

        doc.close()
        self._write_csv()
        self._summary()

    def scan_metadata(self, pages=None, progress_callback=None):
        doc = fitz.open(self.pdf_path)
        total = len(doc)
        plist = pages if pages is not None else list(range(total))

        print("  Scanning page-wise specifications...")
        for i, pno in enumerate(plist):
            self._page_meta[pno] = self.meta_extractor.extract_page_meta(doc, pno)
            if progress_callback:
                progress_callback(int((i + 1) / len(plist) * 100), 100)

        doc.close()
        self._write_page_metadata()

    def _write_page_metadata(self):
        meta_path = self.output_dir / "pages_metadata.json"
        # Convert numeric keys to string for JSON
        data = {str(pno + 1): meta for pno, meta in self._page_meta.items()}
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _process_spatial(self, doc, pno, info):
        xref = info.get('xref')
        if not xref: xref = doc[pno].get_images()[info['number']][0]
        
        # We NO LONGER match per-image. Just extract the image.
        try:
            d = doc.extract_image(xref)
            img_bytes, ext = prepare_output(d['image'], d['ext'])
            if not img_bytes: return
            h = hashlib.md5(img_bytes).hexdigest()
            if h in self.seen_hashes:
                self.stats["skipped_dup"] += 1
                return
            img = Image.open(io.BytesIO(img_bytes))
            rej = self.tile_filter.should_reject(img)
            if rej:
                self.stats["skipped_filter"] += 1
                self._reject_log[rej] = self._reject_log.get(rej, 0) + 1
                return
            self.seen_hashes.add(h)
            fname = f"tile_p{pno+1:04d}_{img.width}x{img.height}_{xref}.{ext}"
            (self.output_dir / fname).write_bytes(img_bytes)
            self._csv_rows.append({
                "filename": fname, 
                "page": pno+1, 
                "width_px": img.width, 
                "height_px": img.height, 
                "size_bytes": len(img_bytes),
                "hash": h
            })
            self.stats["tiles_saved"] += 1
        except Exception:
            self.stats["errors"] += 1

    def _write_csv(self):
        if not self._csv_rows: return
        fields = ["filename", "page", "width_px", "height_px", "size_bytes", "hash"]
        with open(self.output_dir / "tiles_report.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self._csv_rows)

    def _summary(self):
        s = self.stats
        print(f"Extraction complete: {s['tiles_saved']} tiles saved, {s['skipped_filter']} filtered.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()
    out = args.output or (Path(args.pdf).stem + "_tiles")
    TileCatalogueExtractor(args.pdf, out).extract()

if __name__ == "__main__":
    main()
