from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_setting, set_setting


router = APIRouter()

DEFAULT_SYSTEM_PROMPT = """Kamu adalah asisten virtual resmi untuk layanan informasi pemerintahan Desa (Chatbot Desa).
Tugasmu adalah menjawab pertanyaan warga desa dengan ramah, sopan, dan informatif.
Jawab berdasarkan informasi (Konteks) dokumen di bawah ini ATAU berdasarkan Riwayat Percakapan sebelumnya.
Gunakan bahasa Indonesia yang baik, sopan, dan mudah dimengerti oleh warga dari berbagai kalangan.
Jika menanyakan informasi pelayanan yang tidak tersedia di dalam Konteks, katakan dengan sopan bahwa kamu tidak memiliki informasi tersebut dan sarankan mereka untuk datang langsung ke Balai Desa. Namun, untuk sapaan atau percakapan biasa (seperti nama, kabar), jawablah sewajarnya sesuai Riwayat Percakapan.

ATURAN PENTING:
- Jawab LANGSUNG ke intinya.
- JANGAN mengulang-ulang sapaan (seperti "Halo lagi", "Senang membantu Anda kembali", dll) di setiap balasan jika ini adalah percakapan lanjutan.
- Cukup sapa pengguna di awal percakapan saja, setelah itu langsung berikan jawaban.

Konteks:
{context}

Pertanyaan: {question}

Jawaban:"""


class SystemPromptUpdate(BaseModel):
    prompt: str


@router.get("/system-prompt")
async def get_system_prompt():
    prompt = get_setting("system_prompt", "")
    return {
        "prompt": prompt if prompt else DEFAULT_SYSTEM_PROMPT,
        "is_custom": bool(prompt),
    }


@router.post("/system-prompt")
async def update_system_prompt(data: SystemPromptUpdate):
    prompt = data.prompt.strip()
    if not prompt:
        return JSONResponse(status_code=400, content={"error": "System prompt tidak boleh kosong."})
    if "{context}" not in prompt or "{question}" not in prompt:
        return JSONResponse(
            status_code=400,
            content={"error": "System prompt harus mengandung {context} dan {question} sebagai placeholder."},
        )
    set_setting("system_prompt", prompt)
    return {"message": "System prompt berhasil disimpan."}


@router.post("/system-prompt/reset")
async def reset_system_prompt():
    set_setting("system_prompt", "")
    return {"message": "System prompt berhasil direset ke default."}
