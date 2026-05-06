#!/usr/bin/env python3
"""
Tile Catalogue — Lossless Image Extractor  (v3 — Tile-Aware)
=============================================================
Extracts ONLY tile product images from PDF catalogues.
Handles all tile types: marble, stone, terracotta, ceramic, mosaic,
near-white, near-black, coloured, patterned.

Smart filter logic (tuned for real tile catalogues):
  REJECTED: QR codes, logos, icons      — size + edge density
  REJECTED: Page borders, rule lines    — extreme aspect ratio
  REJECTED: Blank background fills      — near-zero colour + brightness
  REJECTED: Header/footer graphic bars  — extreme aspect ratio
  KEPT:     All tile textures           — marble, stone, terracotta etc.
  KEPT:     All tile sizes              — 300x300 up to 800x1600+
  KEPT:     Square and rectangular      — any normal tile shape

Quality: JPEG -> byte-perfect copy. PNG/raw -> lossless PNG (compress_level=0).

Usage
-----
  python tile_extractor.py catalogue.pdf
  python tile_extractor.py catalogue.pdf -o my_tiles/
  python tile_extractor.py catalogue.pdf -v
  python tile_extractor.py catalogue.pdf --pages 1-10
"""

import argparse
import csv
import datetime
import hashlib
import io
import os
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


# ── Tile Filter ────────────────────────────────────────────────────────────

class TileFilter:
    """
    Two-zone filter tuned for real tile catalogue PDFs.

    LARGE images (short side >= 150px):
      - Blank background detection (near-zero std + bright)
      - QR/logo via edge density > 75

    SMALL images (short side 80-149px) — tile variant thumbnails:
      - QR codes rejected via colour std > 100 (QR std is always 120+)
      - Logos rejected via aspect ratio > 2.5
      - Everything else kept (tile variants have std 20-70)

    This correctly captures the small tile variant thumbnails shown
    alongside the large hero image in catalogue layouts.
    """

    # Absolute minimum — below this is always decoration/icon
    MIN_SHORT_SIDE       = 80     # px — lowered to capture small variants

    # Aspect ratio for all images
    MIN_ASPECT           = 0.18   # too narrow = border/rule line
    MAX_ASPECT           = 5.5    # too wide   = header strip

    # Large image (>=150px) — blank background detection
    BLANK_STD_MAX        = 1.5
    BLANK_BRIGHTNESS_MIN = 180

    # Large image — QR/logo via edge density
    QR_EDGE_THRESHOLD    = 75

    # Small image (80-149px) — QR detection via colour std
    # QR codes always have std > 110. Tile variants have std 20-70.
    SMALL_QR_STD_MIN     = 100
    # Small image — logo detection via aspect ratio
    SMALL_LOGO_ASPECT    = 2.5

    THUMB_SIZE = 128

    def is_tile(self, img_dict: dict) -> tuple[bool, str]:
        w    = img_dict["width"]
        h    = img_dict["height"]
        bpc  = img_dict.get("bpc", 8)
        data = img_dict["image"]

        # Layer 1: bit depth
        if bpc == 1:
            return False, "1-bit mask"

        # Layer 2: minimum size
        short = min(w, h)
        if short < self.MIN_SHORT_SIDE:
            return False, f"too small ({w}x{h}px, min={self.MIN_SHORT_SIDE})"

        # Layer 3: aspect ratio
        aspect = w / h
        if aspect < self.MIN_ASPECT:
            return False, f"too narrow (ratio {aspect:.2f})"
        if aspect > self.MAX_ASPECT:
            return False, f"too wide (ratio {aspect:.2f})"

        # Layer 4+: pixel analysis
        try:
            img = Image.open(io.BytesIO(data))
        except Exception:
            return True, ""

        thumb = img.copy()
        thumb.thumbnail((self.THUMB_SIZE, self.THUMB_SIZE), Image.BOX)
        try:
            rgb = thumb.convert("RGB")
        except Exception:
            return True, ""

        stat       = ImageStat.Stat(rgb)
        color_std  = sum(stat.stddev[:3]) / 3
        brightness = sum(stat.mean[:3]) / 3

        if short >= 150:
            # ── LARGE IMAGE ZONE ──────────────────────────────────────────
            # Blank background: near-uniform AND bright
            if color_std < self.BLANK_STD_MAX and brightness > self.BLANK_BRIGHTNESS_MIN:
                return False, f"blank fill (std={color_std:.1f} bright={brightness:.0f})"

            # QR / logo: very high edge density
            edges = rgb.convert("L").filter(ImageFilter.FIND_EDGES)
            edge_dens = ImageStat.Stat(edges).mean[0]
            if edge_dens > self.QR_EDGE_THRESHOLD:
                return False, f"QR/logo (edges={edge_dens:.0f})"

        else:
            # ── SMALL IMAGE ZONE (80-149px) — tile variant thumbnails ─────
            # QR codes always have extremely high colour std (>110)
            if color_std > self.SMALL_QR_STD_MIN:
                return False, f"QR code (std={color_std:.0f} > {self.SMALL_QR_STD_MIN})"

            # Logos are wide and short (aspect > 2.5)
            if aspect > self.SMALL_LOGO_ASPECT:
                return False, f"logo/banner (aspect={aspect:.2f})"

            # Blank fills
            if color_std < self.BLANK_STD_MAX and brightness > self.BLANK_BRIGHTNESS_MIN:
                return False, f"blank fill (std={color_std:.1f})"

        return True, ""


# ── Format helpers ─────────────────────────────────────────────────────────

def file_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def raw_to_png(data: bytes, w: int, h: int, cs: str) -> bytes:
    mode = {"DeviceGray": "L", "DeviceRGB": "RGB", "DeviceCMYK": "CMYK"}.get(cs, "RGB")
    img = Image.frombytes(mode, (w, h), data)
    if mode == "CMYK":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=0)
    return buf.getvalue()


def ccitt_to_png(data: bytes, w: int, h: int, k: int) -> bytes:
    def _s(v): return struct.pack("<H", v)
    def _l(v): return struct.pack("<I", v)
    comp = 4 if k < 0 else 3
    entries = [(256,3,1,w),(257,3,1,h),(258,3,1,1),(259,3,1,comp),
               (262,3,1,0),(273,4,1,0),(278,3,1,h),(279,4,1,len(data))]
    ifd_off  = 8
    data_off = ifd_off + 2 + len(entries)*12 + 4
    for i,e in enumerate(entries):
        if e[0]==273: entries[i]=(273,4,1,data_off)
    tiff = b"II"+_s(42)+_l(ifd_off)+_s(len(entries))
    for tag,t,c,v in entries: tiff += _s(tag)+_s(t)+_l(c)+_l(v)
    tiff += _l(0)+data
    buf = io.BytesIO()
    Image.open(io.BytesIO(tiff)).save(buf, format="PNG", optimize=False, compress_level=0)
    return buf.getvalue()


def prepare_output(data, ext, flt, w, h, cs, bpc):
    """JPEG/JP2 byte-copied. Everything else -> lossless PNG."""
    if ext in ("jpg","jpeg") or "DCTDecode" in flt:
        return data, "jpg"
    if ext == "jp2" or "JPXDecode" in flt:
        return data, "jp2"
    if ext == "png":
        return data, "png"
    if "JBIG2" in flt or ext == "jbig2":
        try:
            buf = io.BytesIO()
            Image.open(io.BytesIO(data)).save(buf, "PNG", optimize=False, compress_level=0)
            return buf.getvalue(), "png"
        except Exception as e:
            return None, ""
    if "CCITTFaxDecode" in flt or ext == "ccitt":
        try:
            return ccitt_to_png(data, w, h, -1 if "Group4" in flt else 0), "png"
        except Exception:
            return None, ""
    try:
        return raw_to_png(data, w, h, cs), "png"
    except Exception:
        try:
            buf = io.BytesIO()
            Image.open(io.BytesIO(data)).save(buf, "PNG", optimize=False, compress_level=0)
            return buf.getvalue(), "png"
        except Exception:
            return data, ext or "bin"


# ── Extractor ──────────────────────────────────────────────────────────────

class TileCatalogueExtractor:

    def __init__(self, pdf_path: str, output_dir: str, verbose: bool = False):
        self.pdf_path    = pdf_path
        self.output_dir  = Path(output_dir)
        self.verbose     = verbose
        self.tile_filter = TileFilter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seen_hashes: set[str] = set()
        self.stats = {"pages":0,"raw_found":0,"tiles_saved":0,
                      "skipped_dup":0,"skipped_filter":0,"errors":0}
        self._reject_log: dict[str, int] = {}
        self._csv_rows: list[dict] = []   # one row per saved tile

    def extract(self, pages=None, progress_callback=None):
        doc   = fitz.open(self.pdf_path)
        total = len(doc)
        self.stats["pages"] = total
        plist = pages if pages is not None else list(range(total))

        print(f"\n  Tile Catalogue Extractor v3")
        print(f"  {Path(self.pdf_path).name}  ({total} pages)")
        print(f"  Output: {self.output_dir}\n")

        print("  Scanning...", end="\r")
        refs = [(pno, info)
                for pno in plist
                for info in doc[pno].get_images(full=True)]
        self.stats["raw_found"] = len(refs)
        print(f"  {len(refs)} image references across {len(plist)} page(s)\n")

        it = (tqdm(refs, unit="img", desc="  Processing",
                   bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} "
                               "[{elapsed}<{remaining}, {rate_fmt}]")
              if HAS_TQDM else refs)

        for i, (pno, info) in enumerate(it):
            self._process(doc, pno, info)
            if progress_callback:
                progress_callback(i + 1, len(refs))

        doc.close()
        self._summary()

    def _process(self, doc, pno, info):
        xref = info[0]
        try:
            d = doc.extract_image(xref)
        except Exception as e:
            self.stats["errors"] += 1
            if self.verbose: print(f"\n  ! xref {xref} failed: {e}")
            return

        w, h = d["width"], d["height"]

        # Dedup
        hv = file_hash(d["image"])
        if hv in self.seen_hashes:
            self.stats["skipped_dup"] += 1
            if self.verbose: print(f"\n  ~ [{w}x{h}] xref {xref} — duplicate")
            return
        self.seen_hashes.add(hv)

        # Filter
        ok, reason = self.tile_filter.is_tile(d)
        if not ok:
            self.stats["skipped_filter"] += 1
            key = reason.split("(")[0].strip()
            self._reject_log[key] = self._reject_log.get(key, 0) + 1
            if self.verbose: print(f"\n  x [{w}x{h}] xref {xref} — {reason}")
            return

        # Save
        sd, se = prepare_output(d["image"], d.get("ext","png").lower(),
                                d.get("filter",""), w, h,
                                d.get("cs-name","DeviceRGB"), d.get("bpc",8))
        if sd is None:
            self.stats["errors"] += 1
            return

        fname = f"tile_p{pno+1:04d}_{w}x{h}_x{xref}.{se}"
        out_path = self.output_dir / fname
        out_path.write_bytes(sd)
        self.stats["tiles_saved"] += 1
        kb = len(sd)/1024

        # Record row for CSV
        self._csv_rows.append({
            "filename":    fname,
            "page":        pno + 1,
            "width_px":    w,
            "height_px":   h,
            "format":      se.upper(),
            "size_kb":     round(kb, 1),
            "colorspace":  d.get("cs-name", "DeviceRGB"),
            "bpc":         d.get("bpc", 8),
            "xref":        xref,
        })

        if not HAS_TQDM:
            print(f"  OK  {fname}  [{w}x{h}]  {kb:.1f} KB")
        elif self.verbose:
            print(f"\n  OK  {fname}  [{w}x{h}]  {kb:.1f} KB")

    def _write_csv(self):
        if not self._csv_rows:
            return
        csv_path = self.output_dir / "tiles_report.csv"
        fields = ["filename","page","width_px","height_px",
                  "format","size_kb","colorspace","bpc","xref"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self._csv_rows)
        print(f"  CSV report: {csv_path}")

    def _summary(self):
        s = self.stats
        print(f"\n{'='*50}")
        print(f"  Tile Extraction Complete")
        print(f"{'-'*50}")
        print(f"  Pages processed    : {s['pages']}")
        print(f"  Image refs scanned : {s['raw_found']}")
        print(f"  Tiles saved        : {s['tiles_saved']}")
        print(f"  Non-tile filtered  : {s['skipped_filter']}")
        print(f"  Duplicates skipped : {s['skipped_dup']}")
        if s["errors"]:
            print(f"  Errors             : {s['errors']}")
        if self._reject_log:
            print(f"{'-'*50}")
            print(f"  Filter breakdown:")
            for r, c in sorted(self._reject_log.items(), key=lambda x:-x[1]):
                print(f"    {c:4d}x  {r}")
        print(f"{'-'*50}")
        print(f"  Output: {self.output_dir}")
        self._write_csv()
        print(f"{'='*50}\n")
        if s["tiles_saved"] == 0:
            print("  No tiles found. Run with -v to see why each image was rejected.\n")


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_pages(spec: str, total: int) -> list[int]:
    indices = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            indices.update(range(int(a)-1, int(b)))
        else:
            indices.add(int(part)-1)
    return sorted(i for i in indices if 0 <= i < total)


def main():
    ap = argparse.ArgumentParser(
        description="Lossless tile image extractor for PDF catalogues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("pdf",  help="Path to PDF catalogue")
    ap.add_argument("-o", "--output",  default=None,
                    help="Output folder (default: <pdf_name>_tiles/)")
    ap.add_argument("-p", "--pages",   default=None,
                    help="Pages e.g. '1,3,5-10' (default: all)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Show every accept/reject decision")
    args = ap.parse_args()

    if not os.path.isfile(args.pdf):
        sys.exit(f"File not found: {args.pdf}")

    output_dir = args.output or (Path(args.pdf).stem + "_tiles")
    doc_tmp    = fitz.open(args.pdf)
    total      = len(doc_tmp)
    doc_tmp.close()

    pages = parse_pages(args.pages, total) if args.pages else None

    TileCatalogueExtractor(
        pdf_path   = args.pdf,
        output_dir = output_dir,
        verbose    = args.verbose,
    ).extract(pages=pages)


if __name__ == "__main__":
    main()
