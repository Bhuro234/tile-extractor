import os
import csv
import json
import shutil
import uuid
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from tile_extractor import TileCatalogueExtractor

app = FastAPI(title="Tile Extractor API")

JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)

PROGRESS_STATE = {}

def run_extraction_task(job_id: str, pdf_path: str, output_dir: str):
    PROGRESS_STATE[job_id] = {"status": "processing", "current": 0, "total": 0, "percentage": 0}
    try:
        extractor = TileCatalogueExtractor(
            pdf_path=pdf_path,
            output_dir=output_dir,
            verbose=False
        )
        def progress_cb(current, total):
            PROGRESS_STATE[job_id]["current"] = current
            PROGRESS_STATE[job_id]["total"] = total
            if total > 0:
                PROGRESS_STATE[job_id]["percentage"] = int((current / total) * 100)
                
        extractor.extract(progress_callback=progress_cb)
        PROGRESS_STATE[job_id]["status"] = "completed"
        PROGRESS_STATE[job_id]["percentage"] = 100
    except Exception as e:
        PROGRESS_STATE[job_id]["status"] = "error"
        PROGRESS_STATE[job_id]["error"] = str(e)

@app.post("/api/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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
    
    # Run extractor in background
    background_tasks.add_task(run_extraction_task, job_id, str(pdf_path), str(output_dir))
        
    return {"job_id": job_id, "message": "Extraction started."}

@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    if job_id not in PROGRESS_STATE:
        return {"status": "unknown"}
    return PROGRESS_STATE[job_id]

@app.get("/api/results/{job_id}")
async def get_results(job_id: str):
    job_dir = JOBS_DIR / job_id
    csv_path = job_dir / "output" / "tiles_report.csv"
    meta_path = job_dir / "output" / "pages_metadata.json"

    if not csv_path.exists():
        return JSONResponse(status_code=404, content={"error": "Results not ready yet. Still writing files..."})

    # Load images from CSV
    images_by_page = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pno = row["page"]
            images_by_page.setdefault(pno, []).append(row)

    # Load page metadata if available
    page_meta = {}
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            page_meta = json.load(f)

    # Build page-grouped response
    pages = []
    for pno in sorted(images_by_page.keys(), key=lambda x: int(x)):
        meta = page_meta.get(str(pno), {})
        pages.append({
            "page": int(pno),
            "metadata": meta,
            "images": images_by_page[pno]
        })

    return {"pages": pages}


@app.get("/api/images/{job_id}/{filename}")
async def get_image(job_id: str, filename: str):
    image_path = JOBS_DIR / job_id / "output" / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)

@app.get("/api/download/{job_id}")
async def download_all(job_id: str):
    job_dir = JOBS_DIR / job_id
    output_dir = job_dir / "output"
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No output found")
        
    zip_path = job_dir / f"{job_id}.zip"
    
    if not zip_path.exists():
        shutil.make_archive(str(job_dir / job_id), 'zip', str(output_dir))
        
    return FileResponse(
        path=zip_path, 
        media_type="application/zip", 
        filename="extracted_tiles.zip",
        headers={"Content-Disposition": 'attachment; filename="extracted_tiles.zip"'}
    )

# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")
