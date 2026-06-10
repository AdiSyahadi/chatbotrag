import time
import threading
from collections import defaultdict
import asyncio
from app.modules.wa_sender import send_whatsapp_message

# In-memory session store: {session_id: {"messages": [...], "last_active": timestamp, "warning_sent": bool}}
_sessions: dict[str, dict] = {}
_lock = threading.Lock()

# Session expires after 3 minutes (180 seconds)
SESSION_TTL_SECONDS = 180
WARNING_SECONDS = 120
# Maximum messages stored per session (pairs of user+assistant)
MAX_MESSAGES_PER_SESSION = 20

async def monitor_sessions():
    """Background task to monitor session age and send warnings or delete them."""
    warning_text = "Apakah informasi yang saya berikan sudah cukup? Karena tidak ada balasan, percakapan ini akan saya tutup sebentar lagi. Silakan kirim pesan baru jika masih membutuhkan bantuan."
    while True:
        try:
            now = time.time()
            to_delete = []
            to_warn = []
            
            with _lock:
                for sid, session in _sessions.items():
                    age = now - session["last_active"]
                    if age > SESSION_TTL_SECONDS:
                        to_delete.append(sid)
                    elif age >= WARNING_SECONDS and not session.get("warning_sent"):
                        to_warn.append(sid)
                        session["warning_sent"] = True
                        
                for sid in to_delete:
                    del _sessions[sid]
                    
            for sid in to_warn:
                # Send the warning message
                send_whatsapp_message(sid, warning_text)
                
        except Exception as e:
            print("Error in monitor_sessions:", e)
            
        await asyncio.sleep(10)

def _cleanup_expired():
    """Remove sessions that have been inactive longer than TTL."""
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_active"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def get_history(session_id: str) -> list[dict]:
    """Get conversation history for a session. Returns list of {"role": "user"|"assistant", "content": str}."""
    with _lock:
        _cleanup_expired()
        session = _sessions.get(session_id)
        if not session:
            return []
        return list(session["messages"])


def add_message(session_id: str, role: str, content: str):
    """Add a message to a session's history."""
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = {"messages": [], "last_active": time.time(), "warning_sent": False}
        session = _sessions[session_id]
        session["messages"].append({"role": role, "content": content})
        session["last_active"] = time.time()
        session["warning_sent"] = False  # Reset warning status on new activity
        # Trim oldest messages if over limit
        if len(session["messages"]) > MAX_MESSAGES_PER_SESSION:
            session["messages"] = session["messages"][-MAX_MESSAGES_PER_SESSION:]


def format_history_for_prompt(history: list[dict]) -> str:
    """Format conversation history into a string for insertion into the prompt."""
    if not history:
        return ""
    lines = []
    for msg in history:
        prefix = "User" if msg["role"] == "user" else "Asisten"
        lines.append(f"{prefix}: {msg['content']}")
    return "\n".join(lines)
