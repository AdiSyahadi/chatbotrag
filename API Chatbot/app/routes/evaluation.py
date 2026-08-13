from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.modules.evaluation import run_ragas_evaluation, get_ragas_history
import os
import re

def sanitize_error(err_str: str) -> str:
    """Mask sensitive API keys in error strings."""
    # OpenAI, DeepSeek, Anthropic, etc.
    err_str = re.sub(r'sk-[a-zA-Z0-9_-]{20,}', 'sk-[REDACTED]', err_str)
    # Groq
    err_str = re.sub(r'gsk_[a-zA-Z0-9_-]{20,}', 'gsk_[REDACTED]', err_str)
    # Gemini
    err_str = re.sub(r'AIzaSy[a-zA-Z0-9_-]{20,}', 'AIzaSy[REDACTED]', err_str)
    return err_str

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()

# Variable global state untuk melacak status background task dan error
evaluation_state = {
    "is_evaluating": False,
    "last_error": None
}

@router.get("/admin/evaluasi", response_class=HTMLResponse)
async def page_evaluasi(request: Request):
    return templates.TemplateResponse("evaluasi.html", {"request": request, "active_page": "admin_evaluasi"})

@router.get("/api/evaluasi/metrics")
async def get_metrics():
    """Mengambil history evaluasi RAGAS untuk ditampilkan di chart."""
    history = get_ragas_history()
    return {
        "status": "success", 
        "data": history, 
        "is_evaluating": evaluation_state["is_evaluating"],
        "last_error": evaluation_state["last_error"]
    }

def background_evaluation_task():
    global evaluation_state
    try:
        res = run_ragas_evaluation(limit=10)
        if isinstance(res, dict) and "error" in res:
            evaluation_state["last_error"] = sanitize_error(str(res["error"]))
        else:
            evaluation_state["last_error"] = None
    except Exception as e:
        evaluation_state["last_error"] = sanitize_error(str(e))
    finally:
        evaluation_state["is_evaluating"] = False

@router.post("/api/evaluasi/run")
async def run_evaluasi(background_tasks: BackgroundTasks):
    """Memicu proses RAGAS di background."""
    global evaluation_state
    if evaluation_state["is_evaluating"]:
        return JSONResponse(status_code=400, content={"error": "Evaluasi sedang berjalan. Harap tunggu."})
        
    evaluation_state["is_evaluating"] = True
    evaluation_state["last_error"] = None
    background_tasks.add_task(background_evaluation_task)
    return {"message": "Evaluasi RAGAS sedang dijalankan di background. Silakan tunggu beberapa saat."}
