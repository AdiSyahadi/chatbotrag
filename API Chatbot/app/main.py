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
from app.routes import upload, process_rag, ask, documents, settings, system_prompt, whatsapp, admin_api, auth, reviews, evaluation
from app.routes import public_api

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.routes.auth import limiter
from app.modules.auth import create_default_admin

# Initialize database
init_database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_default_admin()
    task = asyncio.create_task(monitor_sessions())
    yield
    task.cancel()

app = FastAPI(title="RAG Chatbot - Gemini", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

from fastapi import Depends, HTTPException
from app.modules.auth import get_current_user, get_secret_key, ALGORITHM
from jose import jwt

async def verify_page_auth(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=303, headers={"Location": "/login"})

admin_dependency = [Depends(get_current_user)]
page_dependency = [Depends(verify_page_auth)]

# Register API routes
app.include_router(upload.router, prefix="/api", tags=["Upload"], dependencies=admin_dependency)
app.include_router(process_rag.router, prefix="/api", tags=["Process"], dependencies=admin_dependency)
app.include_router(ask.router, prefix="/api", tags=["Ask"], dependencies=admin_dependency)
app.include_router(documents.router, prefix="/api", tags=["Documents"], dependencies=admin_dependency)
app.include_router(settings.router, prefix="/api", tags=["Settings"], dependencies=admin_dependency)
app.include_router(system_prompt.router, prefix="/api", tags=["System Prompt"], dependencies=admin_dependency)
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])
app.include_router(public_api.router, prefix="/api/v1", tags=["Public API"])
app.include_router(admin_api.router, prefix="/api/admin", tags=["Admin Handoff"], dependencies=admin_dependency)
app.include_router(logs.router, tags=["logs"], dependencies=admin_dependency)
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(reviews.router, prefix="/api", tags=["Reviews"])
app.include_router(evaluation.router, tags=["Evaluation"], dependencies=admin_dependency)

# ── Page Routes ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, dependencies=page_dependency)
async def page_chat(request: Request):
    return templates.TemplateResponse(request, "chat.html", {"request": request})


@app.get("/upload", response_class=HTMLResponse, dependencies=page_dependency)
async def page_upload(request: Request):
    return templates.TemplateResponse(request, "upload.html", {"request": request})


@app.get("/documents", response_class=HTMLResponse, dependencies=page_dependency)
async def page_documents(request: Request):
    return templates.TemplateResponse(request, "documents.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse, dependencies=page_dependency)
async def page_settings(request: Request):
    return templates.TemplateResponse(request, "settings.html", {"request": request})


@app.get("/system-prompt", response_class=HTMLResponse, dependencies=page_dependency)
async def page_system_prompt(request: Request):
    return templates.TemplateResponse(request, "system_prompt.html", {"request": request})


@app.get("/embed", response_class=HTMLResponse, dependencies=page_dependency)
async def page_embed(request: Request):
    return templates.TemplateResponse(request, "embed.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})

@app.get("/admin/dashboard", response_class=HTMLResponse, dependencies=page_dependency)
async def page_admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "admin_dashboard.html", {"request": request, "active_page": "admin_dashboard"})

@app.get("/admin/reviews", response_class=HTMLResponse, dependencies=page_dependency)
async def page_admin_reviews(request: Request):
    return templates.TemplateResponse(request, "reviews.html", {"request": request, "active_page": "admin_reviews"})
