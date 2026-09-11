# Portfolio Assistant Backend

Backend kecil untuk chatbot portfolio berbasis Gemini/OpenAI-compatible API.

## Security Controls

- API key hanya dibaca dari environment backend (`AI_API_KEY`). Jangan taruh key di `Frontend/.env` atau variabel `VITE_*`.
- CORS dibatasi lewat `ALLOWED_ORIGINS`.
- Rate limit in-memory per IP: default 10 request/menit.
- Batas input default 500 karakter.
- Prompt-injection guard untuk request yang mencoba membuka/mengubah instruksi sistem.
- Output privacy filter menyensor pola nomor Indonesia dan mengarahkan ke email profesional.
- `/health` tidak mengekspos credential.

## Local Run

```powershell
cd D:\Portofolio\Backend_Assistant
copy .env.example .env
# Isi AI_API_KEY di .env backend, bukan di frontend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Chat test:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/chat -ContentType "application/json" -Body '{"message":"Jelaskan proyek RAG Bagas"}'
```

## Tests

```powershell
cd D:\Portofolio\Backend_Assistant
python -m unittest -v
```

## Deployment

Tidak ada deployment otomatis. Deploy hanya boleh dilakukan setelah approval eksplisit dari owner.
