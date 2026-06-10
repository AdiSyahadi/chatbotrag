import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_api_key
from app.modules.rag_chain import build_rag_chain, build_question_with_history
from app.modules.conversation import get_history, add_message, get_session, set_session_status, detect_handoff_intent, get_all_messages
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

    # --- STATE MANAGEMENT & HANDOFF LOGIC ---
    if request.session_id:
        session = get_session(request.session_id)
        status = session["status"] if session else "BOT_HANDLING"
        
        if status == "WAITING_FOR_AGENT":
            add_message(request.session_id, "user", request.message)
            return {"reply": "Mohon tunggu sebentar, petugas desa kami akan segera membalas pesan Anda."}
        elif status == "AGENT_HANDLING":
            add_message(request.session_id, "user", request.message)
            total = len(get_all_messages(request.session_id))
            return {"reply": "_SILENT_", "total": total}
            
        # Cek Frustrasi
        if detect_handoff_intent(request.message):
            set_session_status(request.session_id, "WAITING_FOR_AGENT")
            add_message(request.session_id, "user", request.message)
            handoff_msg = "Sepertinya Anda membutuhkan bantuan lebih lanjut. Saya telah meneruskan obrolan ini ke petugas/admin desa. Mohon tunggu sebentar ya."
            add_message(request.session_id, "system", handoff_msg)
            total = len(get_all_messages(request.session_id))
            return {"reply": handoff_msg, "role": "system", "total": total}

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
    total_messages = 0
    if request.session_id:
        add_message(request.session_id, "user", request.message)
        add_message(request.session_id, "assistant", answer)
        total_messages = len(get_all_messages(request.session_id))

    # Public response — clean, no internals
    return {
        "reply": answer,
        "total": total_messages
    }


@router.get("/chat/{session_id}/poll")
async def poll_chat(session_id: str, last_count: int = 0):
    """Endpoint untuk Web Widget melakukan polling pesan baru (dari Admin)."""
    messages = get_all_messages(session_id)
    new_messages = []
    
    # Jika ada pesan baru lebih dari yang diketahui widget
    if len(messages) > last_count:
        # Ambil pesan-pesan baru tersebut
        for msg in messages[last_count:]:
            # Widget hanya perlu tahu pesan dari ADMIN, BOT, atau SYSTEM
            if msg["sender_type"] in ["ADMIN", "BOT", "SYSTEM"]:
                role_mapping = {
                    "ADMIN": "bot",
                    "BOT": "bot",
                    "SYSTEM": "system"
                }
                new_messages.append({
                    "role": role_mapping[msg["sender_type"]], # Di mata widget, admin tetap tampil di sisi kiri (bot)
                    "text": msg["text"],
                    "real_sender": msg["sender_type"]
                })
                
    return {
        "messages": new_messages,
        "total": len(messages)
    }


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    api_key = get_api_key()
    return {
        "status": "ok",
        "configured": bool(api_key),
    }
