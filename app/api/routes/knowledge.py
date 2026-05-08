from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db.models import KnowledgeFile
from app.services.pdf_processor import process_and_store_pdf
from app.services.s3_client import generate_presigned_url
import os

router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge Base"])

@router.post("/upload")
async def upload_knowledge_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Uploads a PDF, chunks it, and stores it in the vector DB."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        
    try:
        kf = await process_and_store_pdf(file, db)
        return {"message": f"Successfully processed {kf.filename}", "file_id": kf.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
def list_knowledge_files(db: Session = Depends(get_db)):
    """List all uploaded knowledge base files."""
    files = db.query(KnowledgeFile).order_by(KnowledgeFile.uploaded_at.desc()).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "size_bytes": f.file_size_bytes,
            "uploaded_at": f.uploaded_at
        }
        for f in files
    ]

@router.get("/download/{file_id}")
def download_knowledge_file(file_id: int, db: Session = Depends(get_db)):
    """Download a specific PDF file by ID via S3 Presigned URL."""
    kf = db.query(KnowledgeFile).filter(KnowledgeFile.id == file_id).first()
    if not kf:
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        presigned_url = generate_presigned_url(kf.file_path, filename=kf.filename)
        return RedirectResponse(url=presigned_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not generate download link")

@router.get("/view/{file_id}")
def view_knowledge_file(file_id: int, db: Session = Depends(get_db)):
    """View a specific PDF file by ID inline via S3 Presigned URL."""
    kf = db.query(KnowledgeFile).filter(KnowledgeFile.id == file_id).first()
    if not kf:
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        presigned_url = generate_presigned_url(kf.file_path, inline=True)
        return RedirectResponse(url=presigned_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not generate view link")
