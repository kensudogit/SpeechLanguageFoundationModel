import os
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

app = FastAPI(title="Speech Language Foundation Model API")
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")], allow_methods=["GET", "POST"], allow_headers=["*"])
engine = create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg://speech:speech@db:5432/speech"), pool_pre_ping=True)

@app.on_event("startup")
def setup():
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS transcripts (id BIGSERIAL PRIMARY KEY, content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())"))

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if file.content_type not in {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3", "audio/webm", "audio/ogg"}:
        raise HTTPException(415, "Unsupported audio MIME type")
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Audio exceeds 10 MB")
    if not data:
        raise HTTPException(400, "Empty audio")
    if os.getenv("ASR_PROVIDER", "mock") == "whisper":
        from faster_whisper import WhisperModel
        suffix = Path(file.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix) as temp:
            temp.write(data)
            temp.flush()
            model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
            segments, _ = model.transcribe(temp.name, language=os.getenv("ASR_LANGUAGE", "ja"))
            transcript = "".join(segment.text for segment in segments).strip()
    else:
        transcript = "[デモモード] 音声認識モデル未接続です。ASR_PROVIDER=whisper を設定してください。"
    with engine.begin() as conn:
        record_id = conn.execute(text("INSERT INTO transcripts(content) VALUES (:content) RETURNING id"), {"content": transcript}).scalar_one()
    return {"id": record_id, "transcript": transcript, "provider": os.getenv("ASR_PROVIDER", "mock")}

@app.get("/api/transcripts")
def list_transcripts():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, content, created_at FROM transcripts ORDER BY id DESC LIMIT 50"))
        return [{"id": r.id, "content": r.content, "created_at": r.created_at.isoformat()} for r in rows]
