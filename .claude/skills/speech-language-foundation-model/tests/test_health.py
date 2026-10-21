# 実行例: pytest tests/ （backend依存パッケージとhttpx,pytestをインストール）
from fastapi.testclient import TestClient
from backend.app.main import app

def test_health():
    assert TestClient(app).get('/health').json() == {'status': 'ok'}
