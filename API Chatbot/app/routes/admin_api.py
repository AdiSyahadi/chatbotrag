from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_db_connection
from app.modules.conversation import get_all_messages, set_session_status, add_message
from app.modules.wa_sender import send_whatsapp_message

router = APIRouter()

@router.get("/sessions")
def get_sessions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_id, status, last_activity 
        FROM sessions 
        WHERE status != 'BOT_HANDLING'
        ORDER BY last_activity DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    sessions = []
    for r in rows:
        sessions.append(dict(r))
        
    return JSONResponse(content={"sessions": sessions})

@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    messages = get_all_messages(session_id)
    return JSONResponse(content={"messages": messages})

class ReplyRequest(BaseModel):
    message: str

@router.post("/sessions/{session_id}/takeover")
def takeover_session(session_id: str):
    set_session_status(session_id, "AGENT_HANDLING")
    # Kirim notif ke user
    add_message(session_id, "system", "Admin mengambil alih obrolan ini.")
    # Jika sesi WA, bisa kita send WA:
    if "@" in session_id or session_id.isdigit():
        send_whatsapp_message(session_id, "Halo, ini admin desa. Ada yang bisa saya bantu?")
    return JSONResponse(content={"status": "success"})

@router.post("/sessions/{session_id}/reply")
def reply_session(session_id: str, request: ReplyRequest):
    add_message(session_id, "admin", request.message)
    # Kirim pesan via WA API jika formatnya WA
    if "@" in session_id or session_id.isdigit():
        send_whatsapp_message(session_id, request.message)
    return JSONResponse(content={"status": "success", "message": "Terkirim"})

@router.post("/sessions/{session_id}/resolve")
def resolve_session(session_id: str):
    set_session_status(session_id, "BOT_HANDLING")
    closing_msg = "Obrolan dengan admin telah selesai. Anda sekarang terhubung kembali dengan Selacau Bot otomatis."
    add_message(session_id, "system", closing_msg)
    
    if "@" in session_id or session_id.isdigit():
        send_whatsapp_message(session_id, closing_msg)
        
    return JSONResponse(content={"status": "success"})
