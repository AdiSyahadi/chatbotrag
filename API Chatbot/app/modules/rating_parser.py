import json
import os
from app.config import get_api_key

def parse_rating_with_llm(user_message: str):
    """
    Parses a user's message to extract a rating and a review text.
    Returns a dictionary: {"is_rating": bool, "rating": int|null, "review_text": str|null}
    """
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate
    
    api_key = get_api_key()
    if not api_key:
        return {"is_rating": False, "rating": None, "review_text": None}
        
    if api_key.startswith("AIzaSy"):
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.0
        )
    else:
        llm = ChatOpenAI(
            model="deepseek-v4-flash",
            openai_api_key=api_key,
            openai_api_base="https://api.deepseek.com",
            temperature=0.0
        )
    
    prompt = PromptTemplate(
        input_variables=["message"],
        template="""
Anda adalah sistem pengekstrak Ulasan Kepuasan Pelanggan (Rating System).
Pengguna baru saja ditanya: "Seberapa puas Anda dengan jawaban otomatis Selacau Bot (1-5 bintang)?" atau pertanyaan serupa terkait kepuasan.

Tugas Anda:
1. Analisis pesan pengguna berikut: "{message}"
2. Tentukan apakah pesan tersebut berisi umpan balik kepuasan (rating), ATAU apakah itu pertanyaan/percakapan baru (misalnya pengguna malah bertanya syarat KTP, dsb).
3. Jika pengguna bertanya tentang BAGAIMANA CARA MENGISI RATING, anggap itu pertanyaan baru (bukan memberi rating).
4. Jika itu adalah ulasan/rating:
   - Ekstrak angkanya (1-5). Jika pengguna tidak menyebut angka tapi sangat memuji, berikan 5. Jika sangat mengeluh, berikan 1. Pastikan nilai ini HANYA angka (Integer) atau null.
   - Ekstrak teks komentarnya (jika ada, selain angkanya). Jika tidak ada teks tambahan selain angka, kembalikan null.
5. Output HARUS murni berformat JSON tanpa markdown, dengan struktur persis seperti ini:
{{
    "is_rating": true/false,
    "rating": <angka 1-5 atau null (tipe data numerik, BUKAN string)>,
    "review_text": "<teks komentar atau null>"
}}

Contoh 1:
Pesan: "Pelayanan admin bintang 5 sangat mantap"
Output: {{"is_rating": true, "rating": 5, "review_text": "Pelayanan admin sangat mantap"}}

Contoh 2:
Pesan: "Besok kelurahan buka jam berapa?"
Output: {{"is_rating": false, "rating": null, "review_text": null}}

Contoh 3:
Pesan: "Gimana cara kasih rating 5?"
Output: {{"is_rating": false, "rating": null, "review_text": null}}

Contoh 4:
Pesan: "Makasih"
Output: {{"is_rating": true, "rating": null, "review_text": "Makasih"}} (Biarkan rating null jika sentimen netral dan tanpa angka)

Contoh 5:
Pesan: "5"
Output: {{"is_rating": true, "rating": 5, "review_text": null}}
"""
    )
    
    chain = prompt | llm
    
    try:
        response = chain.invoke({"message": user_message})
        # Bersihkan output (kadang LLM menambah markdown ```json)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        result = json.loads(text.strip())
        
        try:
            import sqlite3
            from app.config import DATABASE_PATH
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO debug_logs (msg) VALUES (?)", (f"LLM Output: {text.strip()} | Result: {result}",))
            conn.commit()
            conn.close()
        except Exception as ex:
            print("Failed to debug log:", ex)
            
        rating_raw = result.get("rating")
        rating_val = None
        if rating_raw is not None:
            try:
                import re
                match = re.search(r'\d+', str(rating_raw))
                if match:
                    rating_val = int(match.group())
            except Exception:
                pass
                
        review_text = result.get("review_text")
        if review_text == "" or review_text == "null":
            review_text = None
        
        # Pastikan tipe data aman
        return {
            "is_rating": bool(result.get("is_rating", False)),
            "rating": rating_val,
            "review_text": review_text
        }
    except Exception as e:
        print(f"Error parsing rating with LLM: {e}")
        try:
            import sqlite3
            from app.config import DATABASE_PATH
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO debug_logs (msg) VALUES (?)", (f"Rating Parse Error: {e}",))
            conn.commit()
            conn.close()
        except:
            pass
        # Fallback jika gagal parse, kita asumsikan false agar diproses RAG
        return {"is_rating": False, "rating": None, "review_text": None}
