# WhatsApp AI ChatBot (FastAPI + Gemini/DeepSeek + RAG)

ChatBot cerdas untuk WhatsApp yang ditenagai oleh **Gemini AI** / **DeepSeek AI** dan **Retrieval-Augmented Generation (RAG)** menggunakan ChromaDB. ChatBot ini dirancang khusus untuk berjalan berdampingan dengan **SAAS WA API**.

## Fitur Utama
- **Integrasi Multi-LLM**: Mendukung penggunaan **Gemini AI** (google-genai) dan **DeepSeek AI** (via OpenAI SDK) untuk respon yang cerdas.
- **RAG (Retrieval-Augmented Generation)**: Membaca dokumen PDF/DOCX yang di-upload dan menjawab pertanyaan spesifik berdasarkan pengetahuan di dalam dokumen tersebut.
- **Local Embeddings**: Menggunakan model `all-MiniLM-L6-v2` dari HuggingFace yang berjalan 100% lokal secara gratis dan cepat (tidak memotong kuota API).
- **Integrasi Webhook SAAS WA API**: Menerima _webhook_ langsung dari instance SAAS WA API dan membalas pesan secara otomatis.
- **UI Logs Real-time**: Memantau lalu lintas pesan masuk dan keluar secara langsung dari browser.
- **Support LID (Linked Identity)**: Mampu menerima dan merespon pesan dari nomor-nomor baru berformat LID.

## Persyaratan Sistem
- Python 3.9 atau yang lebih baru.
- Akses ke server SAAS WA API (UnOfficial) yang berjalan secara lokal via Docker.

## Panduan Instalasi Lokal

### 1. Buat Virtual Environment (Opsional tapi sangat disarankan)
Buka terminal/command prompt di dalam folder project ini, lalu jalankan:
```bash
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependencies
Pastikan semua library terpasang:
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Webhook SAAS WA API
Untuk menghubungkan ChatBot ini ke SAAS WA API yang berjalan di dalam Docker, Anda harus mengarahkan Webhook Target ke alamat IP komputer Anda (`host.docker.internal`). 

Pastikan pengaturan Webhook Target di SAAS WA API adalah sebagai berikut:
- **Webhook URL**: `http://host.docker.internal:8000/api/whatsapp/webhook`
- **Events**: Cukup pilih event `message.received`.

### 4. Menjalankan Server ChatBot
**SANGAT PENTING**: Karena SAAS WA API berjalan di dalam Docker, server ChatBot (FastAPI) harus di-bind ke semua IP agar Docker bisa masuk dan mengirimkan data webhooks.

Buka terminal **pertama**, lalu jalankan API Backend:
```bash
cd "API Chatbot"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
_(Server API akan berjalan di port `8000`)_

Buka terminal **kedua**, lalu jalankan Halaman Depan (Landing Page):
```bash
cd landing_page
python server.py
```
_(Landing page akan berjalan di port `5500`)_

### 5. Mengatur API Key & Knowledge Base
1. Buka browser dan pergi ke **Dashboard ChatBot**: [http://127.0.0.1:8000](http://127.0.0.1:8000) (Hindari menggunakan `localhost` untuk mencegah masalah *connection refused* di Windows).
2. Buka menu **Documents** untuk mengupload dokumen PDF/DOCX yang ingin digunakan sebagai bahan hafalan bot (RAG).
3. Buka menu **Pengaturan Bot** dan pastikan Anda mengisi:
   - **Gemini / DeepSeek API Key**: Masukkan API Key dari Gemini (Google AI Studio) atau DeepSeek.
   - **WA API URL**: Contoh `http://localhost:3001/api/v1`
   - **WA API Key**: API Key dari organisasi SAAS WA API Anda.
   - **WA Instance ID**: ID dari instance WA yang sudah terkoneksi.

### 6. Memantau Log Pesan
Anda bisa melihat riwayat pesan masuk dan pesan keluar (lengkap beserta status keberhasilan dan tujuan nomor) secara _real-time_ di:
👉 [http://127.0.0.1:8000/logs](http://127.0.0.1:8000/logs)
Halaman ini akan otomatis me-refresh dirinya setiap 5 detik.
