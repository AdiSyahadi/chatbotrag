import requests
import traceback
from fastapi import APIRouter, Request, BackgroundTasks
from app.config import get_setting, get_api_key
from app.modules.rag_chain import build_rag_chain, build_question_with_history
from app.modules.conversation import get_history, add_message
from app.modules.logger import chat_logger

router = APIRouter()

def process_whatsapp_message(payload: dict):
    try:
        if payload.get("event") != "message.received":
            return

        data = payload.get("data", {})
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
            # Call RAG to get the answer
            try:
                # 1. Fetch history for this specific sender
                history = get_history(sender_log_str)
                # 2. Inject history into the question content
                content_with_history = build_question_with_history(content, history)
                
                rag_chain, retriever = build_rag_chain()
                # Get answer from chain using context-injected question
                answer = rag_chain.invoke(content_with_history)
                
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
        from app.modules.wa_sender import send_whatsapp_message
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
