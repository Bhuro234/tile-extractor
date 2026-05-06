#!/usr/bin/env python3
"""
Tile Catalogue — Simple Page Text Extractor
============================================
Extracts tile images and page text specifications (name, size, surface, wall, face count).
"""

import argparse
import csv
import hashlib
import io
import os
import re
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
        HAS_OCR = False
except ImportError:
    HAS_OCR = False


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
    # Regex patterns for extraction
    SIZE_RE = re.compile(r'(\d{2,4})\s*[xX×]\s*(\d{2,4})\s*(mm|cm)?', re.I)
    
    KNOWN_SURFACES = [
        'full polished', 'hd polished', 'full polish',
        'impression', 'matt', 'matte', 'glossy', 'gloss',
        'satin', 'natural', 'lappato', 'structured',
        'rustic', 'hd gloss', 'sugar', 'carving',
        'soft polished', 'anti-skid',
    ]
    
    WALL_KEYWORDS = ['wall', 'wall & floor', 'wall&floor']
    FLOOR_KEYWORDS = ['floor']

    def __init__(self, pdf_path: str, output_dir: str, verbose: bool = False):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.tile_filter = TileFilter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seen_hashes = set()
        self.stats = {"pages": 0, "raw_found": 0, "tiles_saved": 0, "skipped_dup": 0, "skipped_filter": 0, "errors": 0}
        self._reject_log = {}
        self._csv_rows = []

    def extract(self, pages=None, progress_callback=None):
        doc = fitz.open(self.pdf_path)
        total = len(doc)
        self.stats["pages"] = total
        plist = pages if pages is not None else list(range(total))

        tasks = []
        for pno in plist:
            page = doc[pno]
            # Extract page-level text specifications
            page_text = self._extract_page_text(page)
            
            # Get all images on this page
            for info in page.get_image_info():
                tasks.append((pno, info, page_text))

        self.stats["raw_found"] = len(tasks)
        
        print("  Extracting tiles...")
        it = tqdm(tasks) if HAS_TQDM else tasks
        for i, (pno, info, page_text) in enumerate(it):
            self._process_spatial(doc, pno, info, page_text)
            if progress_callback:
                current_prog = int((i + 1) / len(tasks) * 100)
                progress_callback(current_prog, 100)

        doc.close()
        self._write_csv()
        self._summary()

    def _extract_page_text(self, page):
        """Extract all text from a page."""
        text_list = []
        try:
            for block in page.get_text("dict")["blocks"]:
                if block["type"] == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                text_list.append(text)
        except Exception as e:
            if self.verbose:
                print(f"Error extracting page text: {e}", file=sys.stderr)
        return " ".join(text_list)

    def _extract_specs_from_text(self, text):
        """Extract specifications from page text."""
        if not text:
            return {"name": "-", "size": "-", "surface": "-", "wall": "-", "face_count": "-"}
        
        text_lower = text.lower()
        specs = {"name": "-", "size": "-", "surface": "-", "wall": "-", "face_count": "-"}
        
        # Extract SIZE
        size_match = self.SIZE_RE.search(text)
        if size_match:
            w, h, u = size_match.group(1), size_match.group(2), (size_match.group(3) or 'mm')
            specs["size"] = f"{w}x{h}{u}"
        
        # Extract SURFACE
        for surface in self.KNOWN_SURFACES:
            if surface in text_lower:
                specs["surface"] = surface.title()
                break
        
        # Extract WALL/FLOOR
        for keyword in self.WALL_KEYWORDS:
            if keyword in text_lower:
                specs["wall"] = "Wall & Floor"
                break
        if specs["wall"] == "-":
            for keyword in self.FLOOR_KEYWORDS:
                if keyword in text_lower:
                    specs["wall"] = "Floor"
                    break
        
        # Extract NAME - first capitalized word/phrase (3+ chars)
        words = text.split()
        for word in words:
            clean = word.strip('.,;:!?()[]{}')
            if len(clean) > 2 and any(c.isupper() for c in clean):
                specs["name"] = clean
                break
        
        # Extract FACE COUNT
        face_match = re.search(r'(\d+)\s*(?:face|sides?|surfaces)', text_lower)
        if face_match:
            specs["face_count"] = face_match.group(1)
        
        return specs

    def _process_spatial(self, doc, pno, info, page_text):
        xref = info.get('xref')
        if not xref:
            try:
                xref = doc[pno].get_images()[info['number']][0]
            except:
                return
        
        try:
            d = doc.extract_image(xref)
            img_bytes, ext = prepare_output(d['image'], d['ext'])
            if not img_bytes:
                return
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
            
            # Extract specs from page text
            specs = self._extract_specs_from_text(page_text)
            
            self._csv_rows.append({
                "filename": fname,
                "page": pno+1,
                "width_px": img.width,
                "height_px": img.height,
                "size_bytes": len(img_bytes),
                "hash": h,
                "name": specs.get('name', '-'),
                "size": specs.get('size', '-'),
                "surface": specs.get('surface', '-'),
                "wall": specs.get('wall', '-'),
                "face_count": specs.get('face_count', '-')
            })
            self.stats["tiles_saved"] += 1
        except Exception as e:
            if self.verbose:
                print(f"Error processing image: {e}", file=sys.stderr)
            self.stats["errors"] += 1

    def _write_csv(self):
        if not self._csv_rows:
            return
        fields = ["filename", "page", "width_px", "height_px", "size_bytes", "hash", "name", "size", "surface", "wall", "face_count"]
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
