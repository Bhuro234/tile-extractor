import os
import csv
import json
import shutil
import uuid
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from tile_extractor import TileCatalogueExtractor

app = FastAPI(title="Tile Extractor API")

JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)

PROGRESS_STATE = {}

def run_extraction_task(job_id: str, pdf_path: str, output_dir: str, apply_ocr: bool = False):
    print(f"INFO: Starting extraction for job {job_id} (OCR={apply_ocr})")
    PROGRESS_STATE[job_id] = {"status": "processing", "current": 0, "total": 0, "percentage": 0}
    try:
        extractor = TileCatalogueExtractor(
            pdf_path=pdf_path,
            output_dir=output_dir,
            verbose=True,
            apply_ocr=apply_ocr
        )
        def progress_cb(current, total):
            PROGRESS_STATE[job_id]["percentage"] = current
            PROGRESS_STATE[job_id]["total"] = total
                
        extractor.extract_images(progress_callback=progress_cb)
        PROGRESS_STATE[job_id]["status"] = "completed"
        PROGRESS_STATE[job_id]["percentage"] = 100
        print(f"INFO: Completed extraction for job {job_id}")
    except Exception as e:
        print(f"ERROR: Job {job_id} failed: {e}")
        PROGRESS_STATE[job_id]["status"] = "error"
        PROGRESS_STATE[job_id]["error"] = str(e)

@app.post("/api/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...), apply_ocr: str = Form("false")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    pdf_path = job_dir / file.filename
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    output_dir = job_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    is_ocr = apply_ocr.lower() == 'true'
    background_tasks.add_task(run_extraction_task, job_id, str(pdf_path), str(output_dir), is_ocr)
        
    return {"job_id": job_id, "message": "Extraction started."}

@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    if job_id not in PROGRESS_STATE:
        return {"status": "unknown"}
    return PROGRESS_STATE[job_id]

@app.get("/api/results/{job_id}")
async def get_results(job_id: str):
    job_dir = JOBS_DIR / job_id
    csv_path = job_dir / "output" / "tiles.csv"

    if not csv_path.exists():
        return JSONResponse(status_code=404, content={"error": "Results not ready yet."})

    # Load images from CSV
    images_by_page = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pno = row["page"]
            images_by_page.setdefault(pno, []).append(row)

    # Build page-grouped response
    pages = []
    for pno in sorted(images_by_page.keys(), key=lambda x: int(x)):
        images = images_by_page.get(pno, [])
        pages.append({
            "page": int(pno),
            "images": images
        })

    return {"job_id": job_id, "pages": pages}

@app.get("/api/images/{job_id}/{filename}")
async def get_image(job_id: str, filename: str):
    image_path = (JOBS_DIR / job_id / "output" / filename).absolute()
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)

@app.get("/api/download/{job_id}")
async def download_all(job_id: str):
    job_dir = JOBS_DIR / job_id
    output_dir = job_dir / "output"
    zip_filename = f"tiles_{job_id}"
    zip_path = shutil.make_archive(str(job_dir / zip_filename), 'zip', str(output_dir))
    return FileResponse(zip_path, filename=f"extracted_tiles.zip")

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
