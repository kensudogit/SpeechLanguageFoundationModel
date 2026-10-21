def test_health(client):
    payload = client.get("/health").json()
    assert payload["status"] in {"ok", "degraded"}
    assert "sk-" not in str(payload)
