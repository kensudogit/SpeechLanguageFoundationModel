def test_health_has_no_secret(client):
    payload = client.get("/health").json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["asr_provider"] == "mock"
    assert payload["asr_ready"] is True
    assert payload["websocket"] is True
    assert payload["live_websocket"] is True
    assert payload["auth_required"] is False
    assert payload["training_use"] is False
    assert payload["openai_configured"] is False
    assert "sk-" not in str(payload)


def test_index_is_service_ui(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "会話する" in response.text
    assert "新しい会話" in response.text


def test_transcribe_mock_and_history_delete(client):
    files = {"file": ("hello.wav", b"RIFF....", "audio/wav")}
    created = client.post("/api/transcribe", files=files)
    assert created.status_code == 200
    body = created.json()
    assert body["provider"] == "mock"
    assert "実音声認識はしていません" in body["transcript"]
    assert body["training_use"] is False

    listed = client.get("/api/transcripts").json()
    assert any(item["id"] == body["id"] for item in listed)

    deleted = client.delete(f"/api/transcripts/{body['id']}")
    assert deleted.status_code == 200
    assert client.delete(f"/api/transcripts/{body['id']}").status_code == 404


def test_reject_bad_audio(client):
    assert client.post(
        "/api/transcribe", files={"file": ("a.txt", b"hello", "text/plain")}
    ).status_code == 415
    assert client.post(
        "/api/transcribe", files={"file": ("empty.wav", b"", "audio/wav")}
    ).status_code == 400


def test_dialogue_and_speak_are_mock(client):
    reply = client.post("/api/dialogue", json={"transcript": "今日の予定を確認して"})
    assert reply.status_code == 200
    assert reply.json()["provider"] == "mock"
    assert "デモ応答" in reply.json()["reply"]

    spoken = client.post("/api/speak", json={"text": "確認です"})
    assert spoken.status_code == 200
    assert spoken.headers["content-type"].startswith("audio/wav")
    assert spoken.content[:4] == b"RIFF"


def test_turn_keeps_conversation(client):
    files = {"file": ("hello.wav", b"RIFF....", "audio/wav")}
    first = client.post("/api/turn", files=files)
    assert first.status_code == 200
    body = first.json()
    cid = body["conversation_id"]
    assert "1往復目" in body["reply"]

    second = client.post(
        "/api/turn",
        files=files,
        data={"conversation_id": str(cid)},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == cid
    assert "2往復目" in second.json()["reply"]

    thread = client.get(f"/api/conversations/{cid}").json()
    assert len(thread["messages"]) == 4
    assert thread["messages"][0]["role"] == "user"
    assert thread["messages"][1]["role"] == "assistant"


def test_ws_transcribe_streams_final(client):
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"filename": "stream.wav", "content_type": "audio/wav"})
        ws.send_bytes(b"RIFF....")
        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event.get("type") in {"final", "error"}:
                break
    assert events[0]["type"] == "started"
    assert any(item["type"] == "partial" for item in events)
    assert events[-1]["type"] == "final"
    assert "実音声認識はしていません" in events[-1]["transcript"]


def test_audit_has_no_secret(client):
    client.post("/api/transcribe", files={"file": ("hello.wav", b"RIFF....", "audio/wav")})
    rows = client.get("/api/audit").json()
    assert rows
    assert any(row["action"] == "transcribe" for row in rows)
    assert "sk-" not in str(rows)


def test_ws_live_chunks_then_reply(client):
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "start",
                "filename": "live.webm",
                "content_type": "audio/webm",
                "complete_turn": True,
            }
        )
        assert ws.receive_json()["type"] == "started"
        ws.send_bytes(b"RIFF")
        assert ws.receive_json()["type"] == "chunk_ack"
        ws.send_bytes(b"....")
        assert ws.receive_json()["type"] == "chunk_ack"
        ws.send_json({"type": "end"})
        types = []
        last = None
        while True:
            event = ws.receive_json()
            types.append(event["type"])
            last = event
            if event["type"] in {"reply", "error"}:
                break
    assert "final" in types
    assert last["type"] == "reply"
    assert last["conversation_id"]
    thread = client.get(f"/api/conversations/{last['conversation_id']}").json()
    assert len(thread["messages"]) == 2


def test_conversation_list_and_delete(client):
    created = client.post("/api/conversations").json()
    cid = created["conversation_id"]
    listed = client.get("/api/conversations").json()
    assert any(item["id"] == cid for item in listed)
    assert client.delete(f"/api/conversations/{cid}").status_code == 200
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def test_demo_token_rejects_without_header(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "demo-token")
    denied = client.get("/api/transcripts")
    assert denied.status_code == 401
    allowed = client.get("/api/transcripts", headers={"X-Demo-Token": "demo-token"})
    assert allowed.status_code == 200
    assert "sk-" not in str(allowed.json())


def test_metrics_counts_turn(client):
    before = client.get("/metrics").json()["turn"]
    client.post("/api/turn", files={"file": ("hello.wav", b"RIFF....", "audio/wav")})
    after = client.get("/metrics").json()
    assert after["turn"] == before + 1
    assert after["note"] == "process_counters_not_sla"
    assert "sk-" not in str(after)

