from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.config import get_db_connection
from app.routes.auth import limiter
from app.modules.auth import get_current_user

router = APIRouter()

class ReviewSubmit(BaseModel):
    session_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = ""

@router.post("/v1/rating")
@limiter.limit("2/minute")
async def submit_rating(request: Request, review: ReviewSubmit):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Otorisasi: Validasi session_id dan status
    if review.session_id:
        cursor.execute("SELECT status FROM sessions WHERE session_id = ?", (review.session_id,))
        row = cursor.fetchone()
        if not row or row["status"] != "AWAITING_RATING":
            conn.close()
            return JSONResponse(
                status_code=400,
                content={"error": "Sesi tidak valid atau Anda sudah memberikan ulasan."}
            )
        user_id = review.session_id
    else:
        # Jika tidak ada session_id, tolak (jangan biarkan anonymous IP spam rating)
        conn.close()
        return JSONResponse(
            status_code=400, 
            content={"error": "Sesi percakapan diperlukan untuk memberikan ulasan."}
        )

    # Lakukan INSERT dan UPDATE secara transaksional
    cursor.execute(
        "INSERT INTO ratings (user_id, rating, review_text, source) VALUES (?, ?, ?, ?)",
        (user_id, review.rating, review.review_text, "WEB")
    )
    cursor.execute("UPDATE sessions SET status = 'RESOLVED' WHERE session_id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    
    return JSONResponse(content={"status": "success", "message": "Terima kasih atas ulasan Anda!"})

@router.get("/v1/rating/summary")
def get_rating_summary():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Rata-rata rating
    cursor.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as total FROM ratings WHERE rating IS NOT NULL")
    stats = cursor.fetchone()
    avg_rating = round(stats["avg_rating"], 1) if stats["avg_rating"] else 0.0
    total_reviews = stats["total"]
    
    # Ambil 5 ulasan terbaik (bintang 5) yang ada teksnya
    cursor.execute("""
        SELECT rating, review_text, source, created_at 
        FROM ratings 
        WHERE rating >= 4 AND review_text != '' AND review_text IS NOT NULL
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    top_reviews = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return JSONResponse(content={
        "average": avg_rating,
        "total": total_reviews,
        "recent_top_reviews": top_reviews
    })

@router.get("/admin/reviews")
def get_all_reviews(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, rating, review_text, source, created_at 
        FROM ratings 
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    reviews = []
    for r in rows:
        d = dict(r)
        # Sensor nomor HP warga (contoh: 6281212345678 -> 62812***5678)
        if d["source"] != "WEB" and len(d["user_id"]) > 8:
            uid = d["user_id"]
            d["user_id"] = uid[:5] + "***" + uid[-4:]
        reviews.append(d)
        
    return JSONResponse(content={"reviews": reviews})
