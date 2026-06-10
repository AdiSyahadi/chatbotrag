from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_db_connection, get_api_key
from app.modules.document_loader import load_document
from app.modules.text_splitter import split_documents
from app.modules.vectorstore import save_to_vectorstore


router = APIRouter()


class ProcessRequest(BaseModel):
    document_id: int | None = None  # None = process all unprocessed


@router.post("/process-rag")
async def process_rag(request: ProcessRequest = ProcessRequest()):
    api_key = get_api_key()
    if not api_key:
        return JSONResponse(
            status_code=400,
            content={"error": "API key Gemini belum diatur. Silakan set di halaman Settings."},
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.document_id:
        cursor.execute(
            "SELECT * FROM documents WHERE id = ? AND is_processed = 0",
            (request.document_id,),
        )
    else:
        cursor.execute("SELECT * FROM documents WHERE is_processed = 0")

    docs_to_process = cursor.fetchall()

    if not docs_to_process:
        conn.close()
        return {"message": "Tidak ada dokumen baru yang perlu diproses.", "processed": 0}

    total_chunks = 0
    processed_ids = []

    for doc in docs_to_process:
        try:
            # Load document
            raw_docs = load_document(doc["filepath"])

            # Split into chunks
            chunks = split_documents(raw_docs)

            # Add metadata
            for chunk in chunks:
                chunk.metadata["document_id"] = doc["id"]
                chunk.metadata["filename"] = doc["filename"]

            # Save to vectorstore
            save_to_vectorstore(chunks)

            total_chunks += len(chunks)
            processed_ids.append(doc["id"])

            # Update status
            cursor.execute(
                "UPDATE documents SET is_processed = 1 WHERE id = ?",
                (doc["id"],),
            )
            conn.commit()

        except Exception as e:
            conn.close()
            return JSONResponse(
                status_code=500,
                content={"error": f"Gagal memproses dokumen '{doc['filename']}': {str(e)}"},
            )

    conn.close()

    return {
        "message": f"Berhasil memproses {len(processed_ids)} dokumen menjadi {total_chunks} chunks.",
        "processed": len(processed_ids),
        "total_chunks": total_chunks,
    }
