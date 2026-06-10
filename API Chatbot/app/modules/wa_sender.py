import requests
from app.config import get_setting
from app.modules.logger import chat_logger

def send_whatsapp_message(recipient: str, text: str, fallback_jid: str = ""):
    """Send text message using SAAS WA API."""
    wa_api_url = get_setting("wa_api_url", "").strip()
    wa_api_key = get_setting("wa_api_key", "").strip()
    wa_instance_id = get_setting("wa_instance_id", "").strip()
    
    if not wa_api_url or not wa_api_key or not wa_instance_id:
        print("WA API settings are not configured in DB.")
        return False
        
    if wa_api_url.endswith("/api/v1"):
        send_url = f"{wa_api_url}/messages/send-text"
    else:
        send_url = f"{wa_api_url.rstrip('/')}/api/v1/messages/send-text"
        
    headers = {
        "X-API-Key": wa_api_key,
        "Content-Type": "application/json"
    }
    
    body = {
        "instance_id": wa_instance_id,
        "to": recipient,
        "text": text
    }
    
    print(f"Sending reply to WA API: {send_url}, to: {recipient}")
    try:
        resp = requests.post(send_url, json=body, headers=headers)
        
        # Fallback to JID if it fails and fallback_jid is provided
        if resp.status_code != 200 and resp.status_code != 201 and fallback_jid:
            print(f"WA API failed with recipient {recipient} ({resp.status_code}), trying fallback JID: {fallback_jid}")
            body["to"] = fallback_jid
            resp = requests.post(send_url, json=body, headers=headers)
            
        if resp.status_code != 200 and resp.status_code != 201:
            print("WA API Error Response:", resp.status_code, resp.text)
            chat_logger.add_log("OUTGOING", body["to"], text, f"Failed ({resp.status_code})")
            return False
        else:
            print(f"WA Reply Sent successfully to {body['to']}.")
            chat_logger.add_log("OUTGOING", body["to"], text, "Success")
            return True
            
    except Exception as e:
        print("Exception sending WA message:", e)
        chat_logger.add_log("ERROR", recipient, text, f"Exception: {e}")
        return False
