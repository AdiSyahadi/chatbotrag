import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_api_key
from app.modules.rag_chain import build_rag_chain, build_question_with_history, get_langfuse_handler
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
        
        # Jika sesi sudah selesai sebelumnya, buka sesi baru
        if status == "RESOLVED":
            status = "BOT_HANDLING"
            set_session_status(request.session_id, "BOT_HANDLING")
            
        if status == "WAITING_FOR_AGENT":
            add_message(request.session_id, "user", request.message)
            return {"reply": "Mohon tunggu sebentar, petugas desa kami akan segera membalas pesan Anda."}
        elif status == "AGENT_HANDLING":
            add_message(request.session_id, "user", request.message)
            total = len(get_all_messages(request.session_id))
            return {"reply": "_SILENT_", "total": total}
            
        elif status == "AWAITING_RATING":
            from app.modules.rating_parser import parse_rating_with_llm
            from app.config import get_db_connection
            
            rating_data = parse_rating_with_llm(request.message)
            if rating_data["is_rating"]:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO ratings (user_id, rating, review_text, source) VALUES (?, ?, ?, ?)",
                    (request.session_id, rating_data["rating"], rating_data["review_text"], "WEB_CHAT")
                )
                conn.commit()
                conn.close()
                
                set_session_status(request.session_id, "RESOLVED")
                reply_msg = "Terima kasih banyak atas ulasan Anda! Penilaian Anda sangat berarti bagi kami. 😊"
                add_message(request.session_id, "assistant", reply_msg)
                total = len(get_all_messages(request.session_id))
                return {"reply": reply_msg, "total": total}
            else:
                # Jika user merespons hal lain, kembalikan ke BOT_HANDLING
                set_session_status(request.session_id, "BOT_HANDLING")
            
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

    import re
    # Gratitude trigger for automatic rating
    gratitude_pattern = r'.*(makasih|terima kasih|thanks|terimakasih|oke makasih|ok sip|mantap).*'
    # Hanya trigger jika pesannya relatif pendek (<= 40 karakter) dan bukan pertanyaan (?)
    if len(request.message) <= 40 and "?" not in request.message and re.match(gratitude_pattern, request.message.strip(), re.IGNORECASE) and request.session_id:
        set_session_status(request.session_id, "AWAITING_RATING")
        reply_msg = "Sama-sama! 😊 Boleh minta waktunya sebentar? Silakan berikan penilaian Anda terhadap layanan Chatbot kami di bawah ini:"
        add_message(request.session_id, "assistant", reply_msg)
        total = len(get_all_messages(request.session_id))
        return {"reply": reply_msg, "total": total, "show_rating_form": True}

    try:
        rag_chain, retriever = build_rag_chain()
        source_docs = retriever.invoke(request.message)
        
        # Setup Langfuse handler
        lf_handler = get_langfuse_handler(session_id=request.session_id or "api_request")
        callbacks = [lf_handler] if lf_handler else []

        from langfuse import propagate_attributes
        with propagate_attributes(session_id=request.session_id or "api_request"):
            # Get answer from chain
            answer = rag_chain.invoke(
                enriched_question, 
                config={
                    "callbacks": callbacks
                }
            )
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
                    "real_sender": msg["sender_type"],
                    "show_rating_form": True if "tingkat kepuasan Anda" in msg["text"] else False
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
