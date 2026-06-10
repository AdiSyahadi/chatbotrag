import time
import asyncio
from typing import List, Dict
from app.config import get_db_connection
from app.modules.wa_sender import send_whatsapp_message

SESSION_TTL_SECONDS = 180
WARNING_SECONDS = 120
MAX_MESSAGES_PER_SESSION = 20

# ── Session State Management ──

def get_session(session_id: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def create_or_update_session(session_id: str, status: str = "BOT_HANDLING"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (session_id, status)
        VALUES (?, ?)
        ON CONFLICT(session_id) DO UPDATE SET 
            status=excluded.status, 
            last_activity=CURRENT_TIMESTAMP
    """, (session_id, status))
    conn.commit()
    conn.close()

def set_session_status(session_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (session_id, status)
        VALUES (?, ?)
        ON CONFLICT(session_id) DO UPDATE SET 
            status=excluded.status, 
            last_activity=CURRENT_TIMESTAMP
    """, (session_id, status))
    conn.commit()
    conn.close()

def update_last_activity(session_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET last_activity=CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

# ── Message History ──

def get_history(session_id: str) -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender_type, text 
        FROM messages 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        # map db sender_type ('USER', 'BOT', 'ADMIN') to prompt roles
        role = "user" if r["sender_type"] == "USER" else "assistant"
        history.append({"role": role, "content": r["text"]})
    
    # Trim to MAX
    return history[-MAX_MESSAGES_PER_SESSION:]

def get_all_messages(session_id: str) -> List[Dict]:
    # Digunakan oleh Admin Dashboard
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sender_type, text, timestamp 
        FROM messages 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_message(session_id: str, role: str, content: str):
    # role can be "user", "assistant" (bot), "admin", "system"
    sender_type = "USER"
    if role == "assistant" or role == "bot":
        sender_type = "BOT"
    elif role == "admin":
        sender_type = "ADMIN"
    elif role == "system":
        sender_type = "SYSTEM"
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Pastikan session ada
    cursor.execute("INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,))
    
    cursor.execute("""
        INSERT INTO messages (session_id, sender_type, text)
        VALUES (?, ?, ?)
    """, (session_id, sender_type, content))
    
    cursor.execute("UPDATE sessions SET last_activity=CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
    
    conn.commit()
    conn.close()


def format_history_for_prompt(history: List[Dict]) -> str:
    if not history:
        return ""
    lines = []
    for msg in history:
        prefix = "User" if msg["role"] == "user" else "Asisten"
        lines.append(f"{prefix}: {msg['content']}")
    return "\n".join(lines)


# ── Frustration & Intent Detection ──

def detect_handoff_intent(text: str, current_fallback_count: int = 0) -> bool:
    """
    Returns True jika pesan mengindikasikan ingin bicara dengan manusia,
    atau jika RAG sudah gagal (fallback) terlalu sering (misal 3x).
    """
    text_lower = text.lower()
    # Menggunakan frasa yang lebih spesifik untuk menghindari false-positive seperti "halo admin"
    keywords = [
        "bicara dengan admin", "hubungkan ke admin", "panggil admin", "mana admin", 
        "butuh admin", "bantuan admin", "tanya admin", "chat dengan admin",
        "bicara dengan manusia", "bukan bot", "butuh manusia", "panggil manusia",
        "customer service", "bantuan langsung", "kecewa", "kurang puas", "nggak nyambung", "bot bodoh", "bot goblok"
    ]
    
    for kw in keywords:
        if kw in text_lower:
            # Pengecualian khusus jika ternyata hanya sapaan, meski jarang dengan frasa di atas
            return True
            
    if current_fallback_count >= 3:
        return True
        
    return False


# ── Background Task (Optional for WhatsApp TTL) ──

async def monitor_sessions():
    """Background task to cleanup idle sessions or send warnings."""
    # (Diperbarui agar menggunakan DB jika diperlukan, sementara kita biarkan sederhana)
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Hapus sesi yang lebih dari TTL (hati-hati, ini bisa menghapus riwayat)
            # Untuk skenario Handoff, kita TIDAK otomatis menghapus riwayat, 
            # melainkan biarkan saja, atau set status ke EXPIRED.
            cursor.execute("SELECT session_id FROM sessions WHERE strftime('%s', 'now') - strftime('%s', last_activity) > ?", (SESSION_TTL_SECONDS,))
            expired_sessions = cursor.fetchall()
            
            # Jika ingin menghapus:
            # for s in expired_sessions:
            #    cursor.execute("DELETE FROM messages WHERE session_id=?", (s['session_id'],))
            #    cursor.execute("DELETE FROM sessions WHERE session_id=?", (s['session_id'],))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print("Error in monitor_sessions DB:", e)
        
        await asyncio.sleep(60)
