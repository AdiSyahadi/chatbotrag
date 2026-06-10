"""
Flask server untuk landing page Tanya PMB.
Berdiri sendiri, terpisah dari API bot (FastAPI port 8000).
Menyediakan proxy /api/chat agar widget tidak cross-origin.
"""

from flask import Flask, send_from_directory, request, Response
import requests

app = Flask(__name__, static_folder=".", static_url_path="")

# URL backend RAG bot
BOT_API = "http://localhost:8000"


# ── Serve landing page ─────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ── Proxy ke API bot (same-origin, no CORS issue) ─────────────────
@app.route("/api/chat", methods=["POST"])
def proxy_chat():
    try:
        resp = requests.post(
            f"{BOT_API}/api/v1/chat",
            json=request.get_json(silent=True),
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except requests.exceptions.ConnectionError:
        return {"error": "Bot server tidak aktif."}, 502
    except requests.exceptions.Timeout:
        return {"error": "Bot server timeout."}, 504


@app.route("/api/health", methods=["GET"])
def proxy_health():
    try:
        resp = requests.get(f"{BOT_API}/api/v1/health", timeout=10)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception:
        return {"error": "Bot server tidak aktif."}, 502


if __name__ == "__main__":
    print("Landing page: http://localhost:5500")
    print("Bot API proxy: http://localhost:5500/api/chat")
    app.run(host="0.0.0.0", port=5500, debug=True)
