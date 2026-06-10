import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_api_key
from app.modules.rag_chain import build_rag_chain, build_question_with_history
from app.modules.conversation import get_history, add_message
from app.modules.evaluator import log_evaluation, calculate_similarity_score


router = APIRouter()


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None


@router.post("/ask")
async def ask_question(request: AskRequest):
    if not request.question.strip():
        return JSONResponse(status_code=400, content={"error": "Pertanyaan tidak boleh kosong."})

    api_key = get_api_key()
    if not api_key:
        return JSONResponse(
            status_code=400,
            content={"error": "API key Gemini belum diatur. Silakan set di halaman Settings."},
        )

    start_time = time.time()

    # Build question with conversation history if session exists
    history = get_history(request.session_id) if request.session_id else []
    enriched_question = build_question_with_history(request.question, history)

    try:
        rag_chain, retriever = build_rag_chain()

        # Get source documents from retriever (use original question for better retrieval)
        source_docs = retriever.invoke(request.question)

        # Get answer from chain (use enriched question with history for context-aware answer)
        answer = rag_chain.invoke(enriched_question)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Gagal memproses pertanyaan: {str(e)}"},
        )

    response_time = time.time() - start_time

    # Extract source info
    sources = []
    for doc in source_docs:
        sources.append({
            "content": doc.page_content[:300],
            "filename": doc.metadata.get("filename", "Unknown"),
            "page": doc.metadata.get("page", None),
        })

    similarity_score = calculate_similarity_score(source_docs)

    # Log to evaluation table
    log_evaluation(
        question=request.question,
        answer=answer,
        similarity_score=similarity_score,
        response_time=response_time,
        source_documents=sources,
    )

    # Save Q&A to conversation session
    if request.session_id:
        add_message(request.session_id, "user", request.question)
        add_message(request.session_id, "assistant", answer)

    return {
        "answer": answer,
        "sources": sources,
        "similarity_score": round(similarity_score, 4),
        "response_time": round(response_time, 2),
    }
