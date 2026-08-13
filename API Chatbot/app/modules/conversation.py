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
            
            # 1. Cleanup AWAITING_RATING yang sudah idle > 5 menit (300 detik)
            cursor.execute("""
                UPDATE sessions 
                SET status='RESOLVED', last_activity=CURRENT_TIMESTAMP 
                WHERE status = 'AWAITING_RATING' 
                AND strftime('%s', 'now') - strftime('%s', last_activity) > 300
            """)
            
            # 2. Cari sesi yang lebih dari TTL (3 menit) dan belum pernah diminta rating (hanya yang BOT_HANDLING atau AGENT_HANDLING)
            cursor.execute("""
                SELECT session_id, status FROM sessions 
                WHERE strftime('%s', 'now') - strftime('%s', last_activity) > ? 
                AND status IN ('BOT_HANDLING', 'AGENT_HANDLING')
            """, (SESSION_TTL_SECONDS,))
            
            idle_sessions = cursor.fetchall()
            if idle_sessions:
                print(f"DEBUG monitor_sessions: Found {len(idle_sessions)} idle sessions to ask rating")
            
            sessions_to_notify_rating = []
            sessions_to_notify_closed = []
            
            for s in idle_sessions:
                sid = s['session_id']
                
                can_prompt = True
                
                # Cek apakah sudah pernah rating sukses dalam 7 hari terakhir
                cursor.execute("SELECT created_at FROM ratings WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (sid,))
                last_rating_row = cursor.fetchone()
                
                from datetime import datetime, timedelta
                
                if last_rating_row and last_rating_row["created_at"]:
                    try:
                        last_rating_time = datetime.strptime(last_rating_row["created_at"], "%Y-%m-%d %H:%M:%S")
                        if datetime.utcnow() - last_rating_time < timedelta(days=7):
                            can_prompt = False
                    except Exception:
                        pass
                
                if can_prompt:
                    # Cek flag 24 jam
                    cursor.execute("SELECT last_prompt_time FROM rating_flags WHERE session_id = ?", (sid,))
                    flag_row = cursor.fetchone()
                    if flag_row and flag_row["last_prompt_time"]:
                        try:
                            last_prompt = datetime.strptime(flag_row["last_prompt_time"], "%Y-%m-%d %H:%M:%S")
                            if datetime.utcnow() - last_prompt < timedelta(hours=24):
                                can_prompt = False
                        except Exception:
                            pass
                
                if can_prompt:
                    # Ubah status ke AWAITING_RATING agar pesan berikutnya ditangkap sebagai rating
                    cursor.execute("UPDATE sessions SET status='AWAITING_RATING', last_activity=CURRENT_TIMESTAMP WHERE session_id=?", (sid,))
                    cursor.execute("INSERT OR REPLACE INTO rating_flags (session_id, last_prompt_time) VALUES (?, CURRENT_TIMESTAMP)", (sid,))
                    
                    # Kirim pesan rating jika itu sesi WA
                    if "@" in sid or sid.replace("+", "").isdigit():
                        sessions_to_notify_rating.append(sid)
                else:
                    # Sudah pernah ditanya rating, cukup akhiri sesi tanpa menagih lagi
                    cursor.execute("UPDATE sessions SET status='RESOLVED', last_activity=CURRENT_TIMESTAMP WHERE session_id=?", (sid,))
                    if "@" in sid or sid.replace("+", "").isdigit():
                        sessions_to_notify_closed.append(sid)
            
            conn.commit()
            conn.close()
            
            # Panggil add_message di luar transaksi untuk menghindari deadlock (database is locked)
            for sid in sessions_to_notify_rating:
                msg = "Sesi obrolan otomatis diakhiri karena tidak ada aktivitas selama 3 menit. Jika percakapan ini bermanfaat, seberapa puas Anda dengan layanan Chatbot kami (1-5 bintang)? Anda bisa membalas dengan 'Bintang 5' atau abaikan pesan ini jika ingin memulai topik baru."
                add_message(sid, "assistant", msg)
                
                # Pastikan recipient dalam format yang didukung SAAS WA API
                recipient = sid
                if "@" in sid and not ("@lid" in sid or "@g.us" in sid):
                    recipient = sid.split("@")[0]
                send_whatsapp_message(recipient, msg, fallback_jid=sid)
                
            for sid in sessions_to_notify_closed:
                msg = "Sesi obrolan otomatis diakhiri karena tidak ada aktivitas selama 3 menit. Terima kasih telah menghubungi layanan administrasi Desa Selacau. Silakan kirim pesan baru jika Anda butuh bantuan lagi."
                add_message(sid, "assistant", msg)
                
                recipient = sid
                if "@" in sid and not ("@lid" in sid or "@g.us" in sid):
                    recipient = sid.split("@")[0]
                send_whatsapp_message(recipient, msg, fallback_jid=sid)
                
        except Exception as e:
            print("Error in monitor_sessions DB:", e)
        
        # Cek setiap 30 detik agar lebih responsif terhadap 3 menit (180 detik)
        await asyncio.sleep(30)
