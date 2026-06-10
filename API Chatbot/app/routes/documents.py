import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.config import get_db_connection, UPLOAD_DIR
from app.modules.vectorstore import delete_from_vectorstore


router = APIRouter()


@router.get("/documents")
async def list_documents():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")
    rows = cursor.fetchall()
    conn.close()

    documents = []
    for row in rows:
        documents.append({
            "id": row["id"],
            "filename": row["filename"],
            "file_type": row["file_type"],
            "file_size": row["file_size"],
            "uploaded_at": row["uploaded_at"],
            "is_processed": bool(row["is_processed"]),
        })

    return {"documents": documents}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    doc = cursor.fetchone()

    if not doc:
        conn.close()
        return JSONResponse(status_code=404, content={"error": "Dokumen tidak ditemukan."})

    # Delete chunks from vectorstore (RAG knowledge)
    chunks_deleted = 0
    vectorstore_error = None
    if doc["is_processed"]:
        try:
            chunks_deleted = delete_from_vectorstore(document_id)
        except Exception as e:
            vectorstore_error = str(e)

    # Delete file from disk
    if os.path.exists(doc["filepath"]):
        os.remove(doc["filepath"])

    # Delete from database
    cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()

    result = {
        "message": f"Dokumen '{doc['filename']}' berhasil dihapus.",
        "chunks_deleted": chunks_deleted,
    }
    if vectorstore_error:
        result["vectorstore_error"] = vectorstore_error
    return result
