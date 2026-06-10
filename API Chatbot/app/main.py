from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes import logs
from contextlib import asynccontextmanager
import asyncio
from app.modules.conversation import monitor_sessions

from app.config import init_database, TEMPLATES_DIR, STATIC_DIR
from app.routes import upload, process_rag, ask, documents, settings, system_prompt, whatsapp
from app.routes import public_api

# Initialize database
init_database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(monitor_sessions())
    yield
    task.cancel()

app = FastAPI(title="RAG Chatbot - Gemini", version="1.0.0", lifespan=lifespan)

# CORS — allow external websites to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Register API routes
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(process_rag.router, prefix="/api", tags=["Process"])
app.include_router(ask.router, prefix="/api", tags=["Ask"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(settings.router, prefix="/api", tags=["Settings"])
app.include_router(system_prompt.router, prefix="/api", tags=["System Prompt"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])
app.include_router(public_api.router, prefix="/api/v1", tags=["Public API"])
app.include_router(logs.router, tags=["logs"])


# ── Page Routes ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def page_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/upload", response_class=HTMLResponse)
async def page_upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/documents", response_class=HTMLResponse)
async def page_documents(request: Request):
    return templates.TemplateResponse("documents.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/system-prompt", response_class=HTMLResponse)
async def page_system_prompt(request: Request):
    return templates.TemplateResponse("system_prompt.html", {"request": request})


@app.get("/embed", response_class=HTMLResponse)
async def page_embed(request: Request):
    return templates.TemplateResponse("embed.html", {"request": request})
