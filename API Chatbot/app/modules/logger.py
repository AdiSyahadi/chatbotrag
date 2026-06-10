from datetime import datetime

class ChatLog:
    def __init__(self):
        self.logs = []
    
    def add_log(self, direction: str, recipient: str, content: str, status: str = "Success"):
        self.logs.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "direction": direction,
            "recipient": recipient,
            "content": content,
            "status": status
        })
        # Keep only the last 100 logs
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]

chat_logger = ChatLog()
