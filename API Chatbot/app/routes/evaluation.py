from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.modules.evaluation import run_ragas_evaluation, get_ragas_history
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()

# Variable global sederhana untuk melacak status background task
is_evaluating = False

@router.get("/admin/evaluasi", response_class=HTMLResponse)
async def page_evaluasi(request: Request):
    return templates.TemplateResponse("evaluasi.html", {"request": request, "active_page": "admin_evaluasi"})

@router.get("/api/evaluasi/metrics")
async def get_metrics():
    """Mengambil history evaluasi RAGAS untuk ditampilkan di chart."""
    history = get_ragas_history()
    return {"status": "success", "data": history, "is_evaluating": is_evaluating}

def background_evaluation_task():
    global is_evaluating
    try:
        run_ragas_evaluation(limit=10)
    finally:
        is_evaluating = False

@router.post("/api/evaluasi/run")
async def run_evaluasi(background_tasks: BackgroundTasks):
    """Memicu proses RAGAS di background."""
    global is_evaluating
    if is_evaluating:
        return JSONResponse(status_code=400, content={"error": "Evaluasi sedang berjalan. Harap tunggu."})
        
    is_evaluating = True
    background_tasks.add_task(background_evaluation_task)
    return {"message": "Evaluasi RAGAS sedang dijalankan di background. Silakan tunggu beberapa saat."}
