# Omnichannel AI Helpdesk (WhatsApp & Web Widget)

Sistem Chatbot Helpdesk kelas Enterprise yang ditenagai oleh **Gemini AI** / **DeepSeek AI** dengan arsitektur **Retrieval-Augmented Generation (RAG)**. Dirancang untuk melayani secara asinkron multi-platform, memadukan interaksi otomatis bot dengan pengambilalihan langsung oleh admin manusia (Live Handoff).

## 🚀 Fitur Utama (Enterprise Features)

- **Omnichannel Support**: 
  - Mendukung penerimaan pesan dari **SAAS WA API** (WhatsApp).
  - Menyediakan **Web Chat Widget** (`landing_page/widget.js`) yang interaktif untuk website instansi/perusahaan.
- **Multi-LLM & RAG Integration**: Mendukung Google Gemini dan DeepSeek secara bergantian. Mampu membaca dokumen PDF/DOCX (Knowledge Base) dan mengekstrak jawaban akurat berbasis lokal _embeddings_ (`all-MiniLM-L6-v2`) yang cepat dan aman.
- **RAGAS Evaluation System**: Evaluasi performa jawaban bot secara periodik menggunakan standar _Faithfulness_ dan _Answer Relevancy_. Membantu mengukur tingkat halusinasi LLM.
- **Langfuse Observability**: Melacak siklus hidup _prompt_, biaya token, dan latensi secara _real-time_ untuk menunjang audit _Backend_.
- **Sistem Live Handoff**: Bot pintar mendeteksi niat (Intent) pengguna ketika ingin berbicara dengan staf manusia dan secara otomatis meneruskan obrolan ke dasbor _Admin_.
- **User Feedback & Rating**: Pengguna dapat memberikan penilaian kepuasan (Bintang 1-5) via Web atau WA, ditangani langsung oleh sistem penangkal duplikasi atomik SQLite (Anti-Spam).

## 💻 Persyaratan Sistem
- Python 3.9 atau lebih baru.
- Instance Docker SAAS WA API (Opsional, jika ingin mengaktifkan kanal WhatsApp).
- OS Linux / Windows / MacOS.

## 🛠 Panduan Instalasi Lokal

### 1. Buat Virtual Environment (Disarankan)
Buka terminal di root direktori proyek, lalu jalankan:
```bash
python -m venv venv
# Aktifkan di Windows:
venv\Scripts\activate
# Aktifkan di Mac/Linux:
source venv/bin/activate
```

### 2. Install Dependencies
Pastikan _compiler_ C++ (Build Tools) tersedia jika Anda meng-install pustaka LLM/ChromaDB.
```bash
pip install -r requirements.txt
```

### 3. Menjalankan Server API (Backend)
Buka terminal **pertama**, lalu jalankan API Backend dengan Uvicorn:
```bash
cd "API Chatbot"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
_Catatan: Penggunaan `0.0.0.0` wajib dilakukan jika Anda menautkannya ke webhook Docker (contoh: host.docker.internal)._

### 4. Menjalankan Landing Page & Web Widget (Frontend)
Buka terminal **kedua**, jalankan server web statis:
```bash
cd landing_page
python server.py
```
*(Landing page akan terbuka di `http://127.0.0.1:5500`)*

## 🔐 Konfigurasi Awal & Kredensial Default

Setelah server menyala, Anda wajib masuk ke Dasbor Admin yang dilindungi sistem autentikasi JWT:
👉 **Akses Dasbor Login**: [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login)

**Kredensial Default:**
- **Username:** `admin`
- **Password:** `admin123`

> [!WARNING]  
> **Keamanan**: Segera ubah sandi Anda di *database* atau fitur profil setelah sistem berjalan di ranah produksi (_Production_).

### Mengisi API Keys
Setelah masuk ke Dasbor, pergi ke menu **Pengaturan Bot** dan pastikan Anda melengkapi:
- **Gemini / DeepSeek API Key**
- **Langfuse Public, Secret, & Host** (Jika ingin mengaktifkan fitur Telemetri Evaluasi)
- **WA API URL, Key, dan Instance ID** (Jika terhubung ke SAAS WA API)

## 📊 Memantau Sistem (Observability)

Sistem ini memiliki beberapa titik pantau (Dashboard) yang bisa diakses oleh Admin:
1. **Chat Logs (`/logs`)**: Pantau laju pesan asinkron antara pengguna Web/WA dengan bot/manusia.
2. **Evaluasi LLM (`/evaluasi`)**: Jalankan *batch processing* menggunakan RAGAS framework. Pastikan koneksi internet stabil karena pengecekan metrik akan menghubungi API DeepSeek.
3. **Ulasan Warga (`/admin/reviews`)**: Memantau tingkat kepuasan (Rating 1-5).
4. **Knowledge Base (`/documents`)**: Tempat Anda menanam memori (hafalan file PDF/DOCX) baru ke dalam basis vektor ChromaDB.
