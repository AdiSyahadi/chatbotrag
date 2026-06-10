from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_api_key, set_api_key, get_setting, set_setting


router = APIRouter()

MIN_API_KEY_LENGTH = 20

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def validate_gemini_key(api_key: str) -> str | None:
    """Test API key dengan request ringan. Return None jika valid, error message jika invalid."""
    try:
        if api_key.startswith("AIzaSy"):
            # Gunakan Gemini
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=api_key,
                max_tokens=5,
            )
        else:
            # Gunakan DeepSeek (default)
            llm = ChatOpenAI(
                model="deepseek-chat",
                openai_api_key=api_key,
                openai_api_base=DEEPSEEK_BASE_URL,
                max_tokens=5,
            )
            
        llm.invoke("test")
        return None
    except Exception as e:
        error_msg = str(e).lower()
        # Quota/limit/credits habis = key valid, hanya saldo habis
        if "quota" in error_msg or "limit" in error_msg or "resource_exhausted" in error_msg or "exhausted" in error_msg or "depleted" in error_msg:
            return None  # Key valid, kredit saja yang habis
        if "api key" in error_msg or "invalid" in error_msg or "permission" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
            return "API key tidak valid. Pastikan key yang dimasukkan benar."
        return f"Gagal memverifikasi API key: {str(e)}"


class SettingsUpdate(BaseModel):
    gemini_api_key: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    top_k: int | None = None
    wa_api_url: str | None = None
    wa_api_key: str | None = None
    wa_instance_id: str | None = None


@router.get("/settings")
async def get_settings():
    api_key = get_api_key()
    return {
        "gemini_api_key_set": bool(api_key),
        "gemini_api_key_preview": ("•" * min(len(api_key) - 5, 20)) + api_key[-5:] if api_key and len(api_key) > 5 else "",
        "chunk_size": int(get_setting("chunk_size", "1000")),
        "chunk_overlap": int(get_setting("chunk_overlap", "200")),
        "top_k": int(get_setting("top_k", "4")),
        "wa_api_url": get_setting("wa_api_url", ""),
        "wa_api_key": get_setting("wa_api_key", ""),
        "wa_instance_id": get_setting("wa_instance_id", ""),
    }


@router.post("/settings")
async def update_settings(settings: SettingsUpdate):
    if settings.gemini_api_key is not None:
        key = settings.gemini_api_key.strip()
        if not key:
            return JSONResponse(status_code=400, content={"error": "API key tidak boleh kosong."})
        if len(key) < MIN_API_KEY_LENGTH:
            return JSONResponse(status_code=400, content={"error": f"API key terlalu pendek. Minimal {MIN_API_KEY_LENGTH} karakter."})
        error = validate_gemini_key(key)
        if error:
            return JSONResponse(status_code=400, content={"error": error})
        set_api_key(key)

    if settings.chunk_size is not None:
        if settings.chunk_size < 100 or settings.chunk_size > 10000:
            return JSONResponse(status_code=400, content={"error": "Chunk size harus antara 100-10000."})
        set_setting("chunk_size", str(settings.chunk_size))

    if settings.chunk_overlap is not None:
        if settings.chunk_overlap < 0 or settings.chunk_overlap > 5000:
            return JSONResponse(status_code=400, content={"error": "Chunk overlap harus antara 0-5000."})
        set_setting("chunk_overlap", str(settings.chunk_overlap))

    if settings.top_k is not None:
        if settings.top_k < 1 or settings.top_k > 20:
            return JSONResponse(status_code=400, content={"error": "Top K harus antara 1-20."})
        set_setting("top_k", str(settings.top_k))

    if settings.wa_api_url is not None:
        set_setting("wa_api_url", settings.wa_api_url.strip())
    if settings.wa_api_key is not None:
        set_setting("wa_api_key", settings.wa_api_key.strip())
    if settings.wa_instance_id is not None:
        set_setting("wa_instance_id", settings.wa_instance_id.strip())

    return {"message": "Pengaturan berhasil disimpan."}
