import json
import urllib.request

health = json.load(urllib.request.urlopen("http://127.0.0.1:8000/health"))
print(
    "health",
    {
        k: health[k]
        for k in ("status", "db", "asr_ready", "live_websocket", "auth_required")
    },
)
created = json.loads(
    urllib.request.urlopen(
        urllib.request.Request(
            "http://127.0.0.1:8000/api/conversations", method="POST", data=b""
        )
    ).read().decode()
)
print("conversation", created["conversation_id"])
listed = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/conversations"))
print("listed", len(listed))
metrics = json.load(urllib.request.urlopen("http://127.0.0.1:8000/metrics"))
print("metrics", {k: metrics[k] for k in ("turn", "ws_live", "note")})
