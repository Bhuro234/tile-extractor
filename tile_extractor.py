#!/usr/bin/env python3
import os
import csv
import io
import hashlib
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
import cv2
import numpy as np

class TileCatalogueExtractor:
    def __init__(self, pdf_path: str, output_dir: str, verbose: bool = False, apply_ocr: bool = False):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.apply_ocr = apply_ocr
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.seen_hashes = set()
        self.stats = {"pages": 0, "tiles_saved": 0, "skipped_dup": 0, "skipped_small": 0}
        self._csv_rows = []

    def extract_images(self, progress_callback=None):
        """Extract all images from the PDF while avoiding duplicates and small icons."""
        doc = fitz.open(self.pdf_path)
        total_pages = len(doc)
        self.stats["pages"] = total_pages
        
        seen_xrefs = set()

        for pno in range(total_pages):
            page = doc[pno]
            
            # If OCR is manually toggled ON, run optical boundaries IN ADDITION to XREF
            if self.apply_ocr:
                self._extract_from_flat_page(page, pno)
                if progress_callback:
                    progress_callback(int((pno + 1) / total_pages * 50), 100) # Half progress for OCR phase
            
            # Use full=True to get the xref directly in the first element of each tuple
            images = page.get_images(full=True)
            
            for img_info in images:
                xref = img_info[0]
                
                # If we've already processed this image object in this PDF, skip it
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                
                try:
                    # Extract the image using its unique reference ID
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    ext = base_image["ext"]
                    w = base_image["width"]
                    h = base_image["height"]
                    
                    # Filter out tiny images (icons, logos, etc.)
                    if w < 100 or h < 100:
                        self.stats["skipped_small"] += 1
                        continue
                        
                    # Use MD5 to check for identical images across different xrefs (common in PDFs)
                    h_hash = hashlib.md5(image_bytes).hexdigest()
                    if h_hash in self.seen_hashes:
                        self.stats["skipped_dup"] += 1
                        continue
                    self.seen_hashes.add(h_hash)

                    # Save the image
                    filename = f"tile_p{pno+1:04d}_{w}x{h}_{xref}.{ext}"
                    (self.output_dir / filename).write_bytes(image_bytes)
                    
                    self._csv_rows.append({
                        "page": pno + 1,
                        "filename": filename,
                        "width": w,
                        "height": h,
                        "size": len(image_bytes),
                        "format": ext.upper(),
                        "method": "XREF"
                    })
                    self.stats["tiles_saved"] += 1
                    
                except Exception as e:
                    if self.verbose:
                        print(f"Error extracting image {xref} on page {pno+1}: {e}")
                    continue
            
            if progress_callback:
                # Update progress (0-100)
                progress_callback(int((pno + 1) / total_pages * 100), 100)
        
        # Write CSV report
        self._write_csv()
        doc.close()
        return self.stats["tiles_saved"]

    def _extract_from_flat_page(self, page, pno):
        """Fallback method: Render page and use OpenCV to crop tiles out of flat catalog pages."""
        if self.verbose:
            print(f"INFO: Page {pno+1} appears flat. Triggering OpenCV boundary extraction...")
            
        # Render page at 3x zoom for high quality crops
        zoom_mat = fitz.Matrix(3, 3)
        pix = page.get_pixmap(matrix=zoom_mat)
        
        # Convert PyMuPDF pixmap to OpenCV numpy array
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:  # RGBA to RGB
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
        
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        
        # Edge detection & Morphological closing to find complete tile boundaries
        edges = cv2.Canny(gray, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        page_area = pix.w * pix.h
        
        for i, cnt in enumerate(contours):
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            
            # Minimum size filter (ignore text blocks or tiny icons)
            if w < 150 or h < 150:
                self.stats["skipped_small"] += 1
                continue
                
            # Maximum size filter: Ignore crops > 50% of the page size (prevents cropping the entire background)
            if area > (page_area * 0.5):
                continue
                
            # Crop the tile from the original high-res array
            crop_img = img_np[y:y+h, x:x+w]
            
            # --- Strip Splitting Logic ---
            # If the block is very wide, it might be multiple tiles joined by thin white lines
            if w / h > 1.5:
                crop_gray = gray[y:y+h, x:x+w]
                col_means = np.mean(crop_gray, axis=0)
                col_stds = np.std(crop_gray, axis=0)
                
                # Find columns that are uniform and either very bright or very dark
                sep_cols = np.where((col_stds < 20) & ((col_means > 230) | (col_means < 25)))[0]
                
                if len(sep_cols) > 0:
                    splits = [0]
                    current_group = []
                    for col in sep_cols:
                        if not current_group or col == current_group[-1] + 1:
                            current_group.append(col)
                        else:
                            splits.append(current_group[len(current_group)//2])
                            current_group = [col]
                    if current_group:
                        splits.append(current_group[len(current_group)//2])
                    splits.append(w)
                    
                    # Filter splits that are too close to each other
                    filtered_splits = [splits[0]]
                    for s in splits[1:]:
                        if s - filtered_splits[-1] > 100:
                            filtered_splits.append(s)
                        else:
                            filtered_splits[-1] = s
                            
                    if len(filtered_splits) > 2: # At least one split found in the middle
                        for j in range(len(filtered_splits)-1):
                            sx1, sx2 = filtered_splits[j], filtered_splits[j+1]
                            sub_crop = crop_img[:, sx1:sx2]
                            
                            if sub_crop.shape[1] > 50:
                                sub_h, sub_w = sub_crop.shape[:2]
                                success, buffer = cv2.imencode(".png", cv2.cvtColor(sub_crop, cv2.COLOR_RGB2BGR))
                                if not success: continue
                                
                                image_bytes = buffer.tobytes()
                                h_hash = hashlib.md5(image_bytes).hexdigest()
                                if h_hash in self.seen_hashes:
                                    self.stats["skipped_dup"] += 1
                                    continue
                                    
                                self.seen_hashes.add(h_hash)
                                filename = f"tile_flat_p{pno+1:04d}_{sub_w}x{sub_h}_{j}_{h_hash[:6]}.png"
                                (self.output_dir / filename).write_bytes(image_bytes)
                                
                                self._csv_rows.append({
                                    "page": pno + 1,
                                    "filename": filename,
                                    "width": sub_w,
                                    "height": sub_h,
                                    "size": len(image_bytes),
                                    "format": "PNG",
                                    "method": "OCR"
                                })
                                self.stats["tiles_saved"] += 1
                        
                        continue # Skip saving the full strip since we saved its sub-crops

            # --- Standard Crop Saving ---
            success, buffer = cv2.imencode(".png", cv2.cvtColor(crop_img, cv2.COLOR_RGB2BGR))
            if not success:
                continue
                
            image_bytes = buffer.tobytes()
            
            # Deduplication
            h_hash = hashlib.md5(image_bytes).hexdigest()
            if h_hash in self.seen_hashes:
                self.stats["skipped_dup"] += 1
                continue
            self.seen_hashes.add(h_hash)
            
            # Save the crop
            filename = f"tile_flat_p{pno+1:04d}_{w}x{h}_{i}.png"
            (self.output_dir / filename).write_bytes(image_bytes)
            
            self._csv_rows.append({
                "page": pno + 1,
                "filename": filename,
                "width": w,
                "height": h,
                "size": len(image_bytes),
                "format": "PNG",
                "method": "OCR"
            })
            self.stats["tiles_saved"] += 1

    def _write_csv(self):
        csv_path = self.output_dir / "tiles.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["page", "filename", "width", "height", "size", "format", "method"])
            writer.writeheader()
            writer.writerows(self._csv_rows)

    def scan_metadata(self, progress_callback=None):
        """Stub for backward compatibility - metadata scanning is removed."""
        if progress_callback:
            progress_callback(100, 100)
        return {}
