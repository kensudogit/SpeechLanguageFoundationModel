"""連続で /api/turn を叩き、成功数だけ数える。p95 や SLA ではない。"""
import json
import urllib.error
import urllib.request

boundary = "----bound"
wav = b"RIFF...."
ok = 0
fail = 0
for i in range(12):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="load{i}.wav"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + wav + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/turn",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            json.loads(resp.read().decode())
            ok += 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        fail += 1
print(json.dumps({"ok": ok, "fail": fail, "note": "count_only_not_sla"}, ensure_ascii=False))
