import requests
import traceback
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, BackgroundTasks
from app.config import get_setting, get_api_key, get_db_connection
from app.modules.rag_chain import build_rag_chain, build_question_with_history, get_langfuse_handler
from app.modules.conversation import get_history, add_message, get_session, set_session_status, detect_handoff_intent
from app.modules.logger import chat_logger
from app.modules.wa_sender import send_whatsapp_message
from app.modules.rating_parser import parse_rating_with_llm

router = APIRouter()

def process_whatsapp_message(payload: dict):
    try:
        if payload.get("event") != "message.received":
            return

        data = payload.get("data", {})
        
        # Deduplication check
        message_id = data.get("id")
        if message_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT message_id FROM processed_webhooks WHERE message_id = ?", (message_id,))
            if cursor.fetchone():
                print(f"Skipping duplicate message: {message_id}")
                conn.close()
                return
            cursor.execute("INSERT INTO processed_webhooks (message_id) VALUES (?)", (message_id,))
            conn.commit()
            conn.close()
            
        chat_jid = data.get("chat_jid") or data.get("from", "")
        # SAAS WA API uses 'type' for message type, not 'message_type'
        message_type = data.get("type") or data.get("message_type", "")
        phone_number = data.get("phone_number", "")
        
        # Determine sender string for log and memory session ID
        sender_log_str = phone_number if phone_number else chat_jid
        
        print(f"Debug: extracted chat_jid={chat_jid}, message_type={message_type}, phone={phone_number}")
        content = data.get("content", "")
        
        # LOG INCOMING MESSAGE FIRST before skipping
        chat_logger.add_log("INCOMING", sender_log_str, content, f"Received ({message_type})")
        
        # Avoid processing non-text or empty messages
        if message_type.upper() != "TEXT" or not content:
            print(f"Skipping message: type={message_type}, content={content}")
            return
            
        wa_api_url = get_setting("wa_api_url", "").strip()
        wa_api_key = get_setting("wa_api_key", "").strip()
        wa_instance_id = get_setting("wa_instance_id", "").strip()
        gemini_api_key = get_api_key()
        
        if not wa_api_url or not wa_api_key or not wa_instance_id:
            msg = "WA API settings are not configured."
            print(msg)
            chat_logger.add_log("ERROR", sender_log_str, "-", msg)
            return
            
        if not gemini_api_key:
            print("API key is not configured.")
            answer = "Maaf, API Key belum diatur di sistem."
        else:
            # ── State Management & Router AI Check ──
            session = get_session(sender_log_str)
            status = session["status"] if session else "BOT_HANDLING"
            
            # Jika sesi sudah selesai sebelumnya, buka sesi baru
            if status == "RESOLVED":
                status = "BOT_HANDLING"
                set_session_status(sender_log_str, "BOT_HANDLING")
            
            if status == "WAITING_FOR_AGENT":
                add_message(sender_log_str, "user", content)
                answer = "Mohon tunggu sebentar, petugas desa kami akan segera membalas pesan Anda."
            elif status == "AGENT_HANDLING":
                add_message(sender_log_str, "user", content)
                # Jangan membalas apa-apa jika agen yang handle
                return
            elif status == "AWAITING_RATING":
                rating_data = parse_rating_with_llm(content)
                if rating_data["is_rating"]:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO ratings (user_id, rating, review_text, source) VALUES (?, ?, ?, ?)",
                        (sender_log_str, rating_data["rating"], rating_data["review_text"], "WA")
                    )
                    conn.commit()
                    conn.close()
                    
                    # Record the user's original rating message into history
                    add_message(sender_log_str, "user", content)
                    
                    set_session_status(sender_log_str, "RESOLVED")
                    answer = "Terima kasih atas ulasan Anda! Penilaian Anda sangat berarti bagi kami."
                    add_message(sender_log_str, "bot", answer)
                    
                    recipient = phone_number or chat_jid.split("@")[0] if "@" in chat_jid else chat_jid
                    send_whatsapp_message(recipient, answer, chat_jid)
                    return
                else:
                    # Jika bukan rating, anggap pertanyaan baru
                    set_session_status(sender_log_str, "BOT_HANDLING")
                    status = "BOT_HANDLING"

            if status == "BOT_HANDLING":
                if detect_handoff_intent(content):
                    set_session_status(sender_log_str, "WAITING_FOR_AGENT")
                    add_message(sender_log_str, "user", content)
                    answer = "Sepertinya Anda membutuhkan bantuan lebih lanjut. Saya telah meneruskan obrolan ini ke petugas/admin desa. Mohon tunggu sebentar ya."
                    add_message(sender_log_str, "bot", answer)
                    
                    recipient = phone_number or chat_jid.split("@")[0] if "@" in chat_jid else chat_jid
                    send_whatsapp_message(recipient, answer, chat_jid)
                    return
                else:
                    # Gratitude trigger
                    gratitude_pattern = r'(makasih|terima kasih|thanks|terima\s*kasih|oke makasih|ok sip|mantap)'
                    # Hanya trigger jika pesannya relatif pendek dan bukan pertanyaan
                    if len(content) <= 40 and "?" not in content and re.search(gratitude_pattern, content.strip(), re.IGNORECASE):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        
                        can_prompt = True
                        
                        # Cek apakah sudah pernah rating sukses dalam 7 hari terakhir
                        cursor.execute("SELECT created_at FROM ratings WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (sender_log_str,))
                        last_rating_row = cursor.fetchone()
                        
                        if last_rating_row and last_rating_row["created_at"]:
                            try:
                                last_rating_time = datetime.strptime(last_rating_row["created_at"], "%Y-%m-%d %H:%M:%S")
                                if datetime.utcnow() - last_rating_time < timedelta(days=7):
                                    can_prompt = False
                            except Exception:
                                pass
                                
                        if can_prompt:
                            cursor.execute("SELECT last_prompt_time FROM rating_flags WHERE session_id = ?", (sender_log_str,))
                            row = cursor.fetchone()
                            if row and row["last_prompt_time"]:
                                try:
                                    last_prompt = datetime.strptime(row["last_prompt_time"], "%Y-%m-%d %H:%M:%S")
                                    if datetime.utcnow() - last_prompt < timedelta(hours=24):
                                        can_prompt = False
                                except Exception:
                                    pass
                        
                        if can_prompt:
                            cursor.execute("INSERT OR REPLACE INTO rating_flags (session_id, last_prompt_time) VALUES (?, CURRENT_TIMESTAMP)", (sender_log_str,))
                            conn.commit()
                            conn.close()
                            
                            set_session_status(sender_log_str, "AWAITING_RATING")
                            answer = "Sama-sama! 😊 Boleh minta waktunya sebentar? Seberapa puas Anda dengan jawaban otomatis Selacau Bot (1-5 bintang)? Anda bisa membalas bebas, misalnya 'Bintang 5 botnya pintar'."
                            add_message(sender_log_str, "bot", answer)
                            
                            recipient = phone_number or chat_jid.split("@")[0] if "@" in chat_jid else chat_jid
                            send_whatsapp_message(recipient, answer, chat_jid)
                            return
                        else:
                            conn.close()
                            
                    # Call RAG to get the answer
                try:
                    # 1. Fetch history for this specific sender
                    history = get_history(sender_log_str)
                    # 2. Inject history into the question content
                    content_with_history = build_question_with_history(content, history)
                    
                    rag_chain, retriever = build_rag_chain()
                    # Setup Langfuse handler
                    lf_handler = get_langfuse_handler(session_id=sender_log_str)
                    callbacks = [lf_handler] if lf_handler else []

                    from langfuse import propagate_attributes
                    with propagate_attributes(session_id=sender_log_str):
                        # Get answer from chain using context-injected question
                        answer = rag_chain.invoke(
                            content_with_history, 
                            config={
                                "callbacks": callbacks
                            }
                        )
                    
                    # 3. Save memory for the next conversation
                    add_message(sender_log_str, "user", content)
                    add_message(sender_log_str, "assistant", answer)
                
                except Exception as e:
                    print("Error in RAG:", e)
                    traceback.print_exc()
                    answer = "Terjadi kesalahan saat memproses pertanyaan Anda di server."

        # PRIORITAS UTAMA: Gunakan nomor HP asli jika tersedia dari webhook (menghindari masalah LID)
        # Fallback ke chat_jid atau extract number
        recipient = phone_number # Coba nomor HP dulu
        if not recipient:
            if "@" in chat_jid:
                recipient = chat_jid.split("@")[0]
            else:
                recipient = chat_jid
        
        print(f"Debug: recipient={recipient}, chat_jid={chat_jid}, phone_number={phone_number}")
        
        # Kirim balasan menggunakan modul wa_sender
        send_whatsapp_message(recipient, answer, chat_jid)
        
    except Exception as e:
        print("Error processing WA message:", e)
        chat_logger.add_log("ERROR", "-", "-", str(e))
        traceback.print_exc()

@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint to receive incoming messages from SAAS WA API
    """
    try:
        payload = await request.json()
        print("Received WA webhook:", payload.get("event"))
        
        # Process message in background to return 200 OK immediately to WhatsApp
        background_tasks.add_task(process_whatsapp_message, payload)
        
        return {"status": "ok"}
    except Exception as e:
        print("Webhook parsing error:", e)
        return {"status": "error", "message": str(e)}
