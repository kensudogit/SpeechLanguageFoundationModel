import io
import math
import os
import struct
import tempfile
import wave
from pathlib import Path

ALLOWED_MIME = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/webm",
    "audio/ogg",
}
MAX_AUDIO_BYTES = 10 * 1024 * 1024
TRAINING_USE = False

_whisper_model = None
_asr_ready = False


def asr_provider() -> str:
    return os.getenv("ASR_PROVIDER", "mock")


def llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock")


def tts_provider() -> str:
    return os.getenv("TTS_PROVIDER", "mock")


def asr_ready() -> bool:
    return _asr_ready


def _load_whisper():
    global _whisper_model
    from faster_whisper import WhisperModel

    _whisper_model = WhisperModel(
        os.getenv("WHISPER_MODEL", "small"),
        device="cpu",
        compute_type="int8",
    )
    return _whisper_model


def warmup() -> dict:
    """Whisper は一度だけ載せる。mock は即 ready。精度は測っていない。"""
    global _asr_ready
    provider = asr_provider()
    if provider == "whisper" and _whisper_model is None:
        _load_whisper()
    _asr_ready = True
    return {
        "asr_provider": provider,
        "asr_ready": True,
        "llm_provider": llm_provider(),
        "tts_provider": tts_provider(),
    }


def mock_transcript(filename: str) -> str:
    label = filename or "audio"
    return (
        f"[デモモード] {label} を受け取りました。実音声認識はしていません。"
        " ASR_PROVIDER=whisper を設定すると faster-whisper を使います。"
    )


def transcribe_audio(data: bytes, filename: str) -> tuple[str, str]:
    provider = asr_provider()
    if provider == "whisper":
        model = _whisper_model or _load_whisper()
        suffix = Path(filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix) as temp:
            temp.write(data)
            temp.flush()
            segments, _ = model.transcribe(
                temp.name, language=os.getenv("ASR_LANGUAGE", "ja")
            )
            text = "".join(segment.text for segment in segments).strip()
        return text or "（無音、または認識結果が空でした）", "whisper"
    return mock_transcript(filename), "mock"


def iter_transcript_events(data: bytes, filename: str):
    """WebSocket 用。最終結果は transcribe_audio と同じ。途中経過はデモ表示。"""
    yield {"type": "started", "filename": filename or "audio"}
    if asr_provider() == "mock":
        yield {"type": "partial", "transcript": f"[デモモード] {filename or 'audio'}"}
    transcript, provider = transcribe_audio(data, filename)
    yield {"type": "final", "transcript": transcript, "provider": provider}


def generate_reply(transcript: str, history: list[dict] | None = None) -> tuple[str, str]:
    provider = llm_provider()
    key = os.getenv("OPENAI_API_KEY", "")
    turns = history or []
    if provider == "openai" and key:
        import httpx

        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        messages = [
            {
                "role": "system",
                "content": "短い日本語で返す。音声認識結果への応答。真の音声理解だと言わない。",
            }
        ]
        for item in turns[-8:]:
            role = item.get("role")
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": str(item.get("content", ""))[:2000]})
        messages.append({"role": "user", "content": transcript[:2000]})
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "max_tokens": 200},
            timeout=30.0,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        return text, "openai"
    snippet = (transcript or "").strip()[:80] or "（空の文字起こし）"
    round_no = (len(turns) // 2) + 1
    return (
        f"[デモ応答] {round_no}往復目。「{snippet}」。"
        " これは音声言語基盤モデルではありません。LLM_PROVIDER=openai でテキスト応答だけ外部送信できます。",
        "mock",
    )


def synthesize_wav(text: str) -> bytes:
    """短い確認音。実音声合成ではない。"""
    _ = text
    rate = 16000
    duration = 0.35
    n = int(rate * duration)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            amp = int(9000 * (1 - i / n))
            sample = int(amp * math.sin(2 * math.pi * 523.25 * i / rate))
            frames += struct.pack("<h", max(-32767, min(32767, sample)))
        wav.writeframes(bytes(frames))
    return buf.getvalue()
