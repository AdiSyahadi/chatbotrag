import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_api_key
from app.modules.rag_chain import build_rag_chain, build_question_with_history
from app.modules.conversation import get_history, add_message
from app.modules.evaluator import log_evaluation, calculate_similarity_score


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
async def public_chat(request: ChatRequest):
    """Public chat endpoint for external UIs.
    Returns only the answer text — no internal metadata exposed.
    """
    if not request.message.strip():
        return JSONResponse(status_code=400, content={"error": "Message tidak boleh kosong."})

    api_key = get_api_key()
    if not api_key:
        return JSONResponse(
            status_code=503,
            content={"error": "Service belum dikonfigurasi."},
        )

    start_time = time.time()

    # Build question with conversation history if session exists
    history = get_history(request.session_id) if request.session_id else []
    enriched_question = build_question_with_history(request.message, history)

    try:
        rag_chain, retriever = build_rag_chain()
        source_docs = retriever.invoke(request.message)
        answer = rag_chain.invoke(enriched_question)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Gagal memproses pertanyaan."},
        )

    response_time = time.time() - start_time
    similarity_score = calculate_similarity_score(source_docs)

    # Log internally
    sources = []
    for doc in source_docs:
        sources.append({
            "content": doc.page_content[:300],
            "filename": doc.metadata.get("filename", "Unknown"),
            "page": doc.metadata.get("page", None),
        })

    log_evaluation(
        question=request.message,
        answer=answer,
        similarity_score=similarity_score,
        response_time=response_time,
        source_documents=sources,
    )

    # Save Q&A to conversation session
    if request.session_id:
        add_message(request.session_id, "user", request.message)
        add_message(request.session_id, "assistant", answer)

    # Public response — clean, no internals
    return {
        "reply": answer,
    }


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    api_key = get_api_key()
    return {
        "status": "ok",
        "configured": bool(api_key),
    }
