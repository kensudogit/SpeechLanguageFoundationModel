import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.auth import auth_required, check_http, check_ws
from app.db import (
    add_audit,
    add_message,
    conversation_exists,
    create_conversation,
    delete_conversation,
    delete_transcript,
    init_schema,
    insert_transcript,
    list_audit,
    list_conversations,
    list_messages,
    list_transcripts,
    make_engine,
    ping,
    prune_older_than,
)
from app.metrics import bump, snapshot as metrics_snapshot
from app.providers import (
    ALLOWED_MIME,
    MAX_AUDIO_BYTES,
    TRAINING_USE,
    asr_provider,
    asr_ready,
    generate_reply,
    iter_transcript_events,
    llm_provider,
    synthesize_wav,
    transcribe_audio,
    tts_provider,
    warmup,
)
from app.rate_limit import allow, limit_per_minute

STATIC_DIR = Path(__file__).resolve().parent / "static"
engine = make_engine()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_schema(engine)
    hours = int(os.getenv("RETENTION_HOURS", "168"))
    prune_older_than(engine, hours)
    warmup()
    yield


app = FastAPI(
    title="Speech Language Foundation Model API",
    description="開発用デモ。モック時は実音声認識をしません。学習利用なし。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class DialogueBody(BaseModel):
    transcript: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None


class SpeakBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "local"


def _read_audio(file: UploadFile, data: bytes) -> None:
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, "対応していない音声形式です")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "音声ファイルは 10MB までです")
    if not data:
        raise HTTPException(400, "空の音声ファイルです")


def _guard(request: Request) -> None:
    try:
        check_http(request)
    except HTTPException:
        bump("denied_401")
        raise


def _run_turn(transcript: str, asr: str, conversation_id: int | None) -> dict:
    cid = conversation_id
    if cid is None:
        cid = create_conversation(engine)
    elif not conversation_exists(engine, cid):
        raise HTTPException(404, "会話が見つかりません")
    history = list_messages(engine, cid)
    insert_transcript(engine, transcript, asr)
    add_message(engine, cid, "user", transcript, asr)
    reply, llm = generate_reply(transcript, history)
    add_message(engine, cid, "assistant", reply, llm)
    add_audit(engine, "turn", True, f"conversation={cid},asr={asr},llm={llm}")
    bump("turn")
    return {
        "conversation_id": cid,
        "transcript": transcript,
        "reply": reply,
        "asr_provider": asr,
        "llm_provider": llm,
        "tts_provider": tts_provider(),
        "training_use": TRAINING_USE,
        "note": "one_turn_not_a_speech_llm",
    }


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    db_ok = False
    try:
        db_ok = ping(engine)
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "asr_provider": asr_provider(),
        "asr_ready": asr_ready(),
        "llm_provider": llm_provider(),
        "tts_provider": tts_provider(),
        "training_use": TRAINING_USE,
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "rate_limit_per_min": limit_per_minute(),
        "auth_required": auth_required(),
        "websocket": True,
        "live_websocket": True,
        "note": "demo_not_a_speech_foundation_model",
    }


@app.get("/metrics")
def metrics():
    return metrics_snapshot()


@app.post("/api/transcribe")
async def transcribe(request: Request, file: UploadFile = File(...)):
    _guard(request)
    if not allow(f"transcribe:{_client_key(request)}"):
        bump("denied_429")
        raise HTTPException(429, "送信が多すぎます。少し待ってから再試行してください")
    data = await file.read(MAX_AUDIO_BYTES + 1)
    try:
        _read_audio(file, data)
        transcript, provider = transcribe_audio(data, file.filename or "audio")
    except HTTPException as exc:
        add_audit(engine, "transcribe", False, str(exc.detail))
        raise
    except Exception as exc:
        add_audit(engine, "transcribe", False, "failed")
        raise HTTPException(502, f"文字起こしに失敗しました: {exc}") from exc
    record_id = insert_transcript(engine, transcript, provider)
    add_audit(engine, "transcribe", True, f"id={record_id},provider={provider}")
    bump("transcribe")
    return {
        "id": record_id,
        "transcript": transcript,
        "provider": provider,
        "training_use": TRAINING_USE,
    }


@app.get("/api/transcripts")
def transcripts(request: Request):
    _guard(request)
    return list_transcripts(engine)


@app.delete("/api/transcripts/{record_id}")
def remove_transcript(request: Request, record_id: int):
    _guard(request)
    if not delete_transcript(engine, record_id):
        add_audit(engine, "delete_transcript", False, f"id={record_id}")
        raise HTTPException(404, "履歴が見つかりません")
    add_audit(engine, "delete_transcript", True, f"id={record_id}")
    return {"deleted": record_id}


@app.delete("/api/transcripts")
def prune_transcripts(
    request: Request, older_than_hours: int = Query(default=None, ge=1, le=1440)
):
    _guard(request)
    hours = older_than_hours or int(os.getenv("RETENTION_HOURS", "168"))
    deleted = prune_older_than(engine, hours)
    add_audit(engine, "prune", True, f"deleted={deleted}")
    return {"deleted": deleted, "older_than_hours": hours}


@app.post("/api/dialogue")
def dialogue(request: Request, body: DialogueBody):
    _guard(request)
    history = []
    if body.conversation_id:
        if not conversation_exists(engine, body.conversation_id):
            raise HTTPException(404, "会話が見つかりません")
        history = list_messages(engine, body.conversation_id)
    try:
        reply, provider = generate_reply(body.transcript, history)
    except Exception as exc:
        add_audit(engine, "dialogue", False, "failed")
        raise HTTPException(502, f"応答生成に失敗しました: {exc}") from exc
    add_audit(engine, "dialogue", True, f"provider={provider}")
    return {
        "reply": reply,
        "provider": provider,
        "training_use": TRAINING_USE,
        "note": "text_only_not_speech_understanding",
    }


@app.post("/api/speak")
def speak(request: Request, body: SpeakBody):
    _guard(request)
    audio = synthesize_wav(body.text)
    add_audit(engine, "speak", True, f"provider={tts_provider()}")
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"X-TTS-Provider": tts_provider(), "X-TTS-Note": "mock-tone-not-speech"},
    )


@app.post("/api/turn")
async def turn(
    request: Request,
    file: UploadFile = File(...),
    conversation_id: int | None = Form(default=None),
):
    _guard(request)
    if not allow(f"turn:{_client_key(request)}"):
        bump("denied_429")
        raise HTTPException(429, "送信が多すぎます。少し待ってから再試行してください")
    data = await file.read(MAX_AUDIO_BYTES + 1)
    try:
        _read_audio(file, data)
        transcript, asr = transcribe_audio(data, file.filename or "audio")
    except HTTPException:
        add_audit(engine, "turn", False, "bad_audio")
        raise
    except Exception as exc:
        add_audit(engine, "turn", False, "asr_failed")
        raise HTTPException(502, f"文字起こしに失敗しました: {exc}") from exc
    try:
        return _run_turn(transcript, asr, conversation_id)
    except HTTPException:
        raise
    except Exception as exc:
        add_audit(engine, "turn", False, "llm_failed")
        raise HTTPException(502, f"応答生成に失敗しました: {exc}") from exc


@app.get("/api/conversations")
def conversations(request: Request):
    _guard(request)
    return list_conversations(engine)


@app.post("/api/conversations")
def new_conversation(request: Request):
    _guard(request)
    cid = create_conversation(engine)
    add_audit(engine, "create_conversation", True, f"id={cid}")
    return {"conversation_id": cid, "messages": []}


@app.get("/api/conversations/{conversation_id}")
def conversation(request: Request, conversation_id: int):
    _guard(request)
    if not conversation_exists(engine, conversation_id):
        raise HTTPException(404, "会話が見つかりません")
    return {
        "conversation_id": conversation_id,
        "messages": list_messages(engine, conversation_id),
    }


@app.delete("/api/conversations/{conversation_id}")
def remove_conversation(request: Request, conversation_id: int):
    _guard(request)
    if not delete_conversation(engine, conversation_id):
        raise HTTPException(404, "会話が見つかりません")
    add_audit(engine, "delete_conversation", True, f"id={conversation_id}")
    return {"deleted": conversation_id}


@app.get("/api/audit")
def audit(request: Request):
    _guard(request)
    return list_audit(engine)


@app.websocket("/ws/transcribe")
async def ws_transcribe(ws: WebSocket):
    await ws.accept()
    if not check_ws(ws):
        bump("denied_401")
        await ws.send_json({"type": "error", "detail": "認証トークンが必要です"})
        await ws.close()
        return
    try:
        meta = await ws.receive_json()
        filename = str(meta.get("filename") or "audio")
        content_type = str(meta.get("content_type") or "")
        audio = await ws.receive_bytes()
        if content_type and content_type not in ALLOWED_MIME:
            await ws.send_json({"type": "error", "detail": "対応していない音声形式です"})
            await ws.close()
            return
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            await ws.send_json({"type": "error", "detail": "音声が空、または 10MB を超えています"})
            await ws.close()
            return
        for event in iter_transcript_events(audio, filename):
            await ws.send_json(event)
            if event.get("type") == "final":
                insert_transcript(engine, event["transcript"], event.get("provider", "mock"))
                add_audit(engine, "ws_transcribe", True, f"provider={event.get('provider')}")
                bump("ws_transcribe")
        await ws.close()
    except WebSocketDisconnect:
        add_audit(engine, "ws_transcribe", False, "disconnect")
    except Exception:
        add_audit(engine, "ws_transcribe", False, "failed")
        try:
            await ws.send_json({"type": "error", "detail": "文字起こしに失敗しました"})
            await ws.close()
        except Exception:
            return


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    if not check_ws(ws):
        bump("denied_401")
        await ws.send_json({"type": "error", "detail": "認証トークンが必要です"})
        await ws.close()
        return
    chunks: list[bytes] = []
    filename = "live.webm"
    content_type = "audio/webm"
    conversation_id = None
    complete_turn = True
    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text") is not None:
                payload = json.loads(message["text"])
                kind = payload.get("type")
                if kind == "start":
                    filename = str(payload.get("filename") or filename)
                    content_type = str(payload.get("content_type") or content_type)
                    conversation_id = payload.get("conversation_id")
                    complete_turn = bool(payload.get("complete_turn", True))
                    if content_type not in ALLOWED_MIME:
                        await ws.send_json({"type": "error", "detail": "対応していない音声形式です"})
                        await ws.close()
                        return
                    await ws.send_json({"type": "started", "filename": filename})
                elif kind == "end":
                    audio = b"".join(chunks)
                    if not audio:
                        await ws.send_json({"type": "error", "detail": "音声が空です"})
                        await ws.close()
                        return
                    for event in iter_transcript_events(audio, filename):
                        await ws.send_json(event)
                        if event.get("type") == "final" and complete_turn:
                            result = _run_turn(
                                event["transcript"],
                                event.get("provider", "mock"),
                                int(conversation_id) if conversation_id else None,
                            )
                            await ws.send_json({"type": "reply", **result})
                    bump("ws_live")
                    add_audit(engine, "ws_live", True, f"chunks={len(chunks)}")
                    await ws.close()
                    return
            elif message.get("bytes") is not None:
                piece = message["bytes"]
                if sum(len(item) for item in chunks) + len(piece) > MAX_AUDIO_BYTES:
                    await ws.send_json({"type": "error", "detail": "音声ファイルは 10MB までです"})
                    await ws.close()
                    return
                chunks.append(piece)
                total = sum(len(item) for item in chunks)
                await ws.send_json(
                    {
                        "type": "chunk_ack",
                        "chunks": len(chunks),
                        "bytes": total,
                        "transcript": f"[デモ途中] {filename} / {len(chunks)}片",
                    }
                )
    except WebSocketDisconnect:
        add_audit(engine, "ws_live", False, "disconnect")
    except Exception:
        add_audit(engine, "ws_live", False, "failed")
        try:
            await ws.send_json({"type": "error", "detail": "ライブへの送信に失敗しました"})
            await ws.close()
        except Exception:
            return

