import os
from io import BytesIO
from pypdf import PdfReader
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.db.models import KnowledgeFile, KnowledgeChunk
from app.services.bedrock_client import generate_embedding_with_bedrock
from app.services.s3_client import upload_file_to_s3

# Ensure uploads directory exists
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks.
    """
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

async def process_and_store_pdf(file: UploadFile, db: Session) -> KnowledgeFile:
    """
    Reads the PDF, saves it to disk, extracts text, chunks it, embeds it using AWS Bedrock,
    and stores everything in the database.
    """
    # 1. Read file bytes and save to disk
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    # 2. Upload to S3 directly
    s3_key = upload_file_to_s3(file_bytes, file.filename)
        
    # 3. Extract text using PyPDF
    reader = PdfReader(BytesIO(file_bytes))
    full_text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            full_text += extracted + "\n"
            
    # 4. Create DB File record
    kf = KnowledgeFile(
        filename=file.filename,
        file_size_bytes=file_size,
        file_path=s3_key
    )
    db.add(kf)
    db.flush()  # To get kf.id
    
    # 4. Chunk and embed
    chunks = _chunk_text(full_text, chunk_size=200, overlap=50) # using smaller chunks of 200 words (~1000 chars)
    
    for chunk_text in chunks:
        # Generate Bedrock embedding (256 dims)
        embedding = generate_embedding_with_bedrock(chunk_text)
        
        # Save to DB
        kc = KnowledgeChunk(
            file_id=kf.id,
            chunk_text=chunk_text,
            embedding=embedding
        )
        db.add(kc)
        
    db.commit()
    db.refresh(kf)
    
    return kf
