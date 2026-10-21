import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.providers import synthesize_wav

wav = synthesize_wav("test")
out = Path(__file__).resolve().parents[1] / "backend" / "app" / "static" / "demo.wav"
out.write_bytes(wav)
boundary = "----bound"
body = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="demo.wav"\r\n'
    "Content-Type: audio/wav\r\n\r\n"
).encode() + wav + f"\r\n--{boundary}--\r\n".encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/transcribe",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
print(urllib.request.urlopen(req).read().decode())
req2 = urllib.request.Request(
    "http://127.0.0.1:8000/api/dialogue",
    data=json.dumps({"transcript": "予定を確認して"}, ensure_ascii=False).encode(),
    headers={"Content-Type": "application/json"},
)
print(urllib.request.urlopen(req2).read().decode())
print(urllib.request.urlopen("http://127.0.0.1:8000/api/transcripts").read().decode())
