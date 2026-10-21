import json
import urllib.request

health = json.load(urllib.request.urlopen("http://127.0.0.1:8000/health"))
print("health", {k: health[k] for k in ("status", "db", "asr_ready", "websocket", "note")})

boundary = "----bound"
wav = b"RIFF...."
body = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="turn.wav"\r\n'
    "Content-Type: audio/wav\r\n\r\n"
).encode() + wav + f"\r\n--{boundary}--\r\n".encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/turn",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
first = json.loads(urllib.request.urlopen(req).read().decode())
print("turn1", first["conversation_id"], first["reply"][:40])

cid = first["conversation_id"]
body2 = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="turn2.wav"\r\n'
    "Content-Type: audio/wav\r\n\r\n"
).encode() + wav + (
    f"\r\n--{boundary}\r\n"
    'Content-Disposition: form-data; name="conversation_id"\r\n\r\n'
    f"{cid}\r\n--{boundary}--\r\n"
).encode()
req2 = urllib.request.Request(
    "http://127.0.0.1:8000/api/turn",
    data=body2,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
second = json.loads(urllib.request.urlopen(req2).read().decode())
print("turn2", second["conversation_id"], second["reply"][:40])
thread = json.load(urllib.request.urlopen(f"http://127.0.0.1:8000/api/conversations/{cid}"))
print("messages", len(thread["messages"]))
