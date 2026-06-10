import os
import shutil
from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import JSONResponse
from app.config import UPLOAD_DIR, get_db_connection
from app.modules.document_loader import is_supported_file

router = APIRouter()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "Nama file tidak valid."})

    if not is_supported_file(file.filename):
        return JSONResponse(
            status_code=400,
            content={"error": "Tipe file tidak didukung. Gunakan PDF, DOCX, atau TXT."},
        )

    # Sanitize filename
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    file_size = os.path.getsize(file_path)
    ext = os.path.splitext(safe_filename)[1].lower()

    # Save metadata to database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO documents (filename, filepath, file_type, file_size)
           VALUES (?, ?, ?, ?)""",
        (safe_filename, file_path, ext, file_size),
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()

    return {
        "message": f"File '{safe_filename}' berhasil diupload.",
        "document_id": doc_id,
        "filename": safe_filename,
        "file_size": file_size,
    }
