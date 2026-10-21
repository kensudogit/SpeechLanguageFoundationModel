# Speech Language Foundation Model

録音またはファイルから、文字起こしと応答を一つの会話として進めるローカルデモです。
Skill は `.claude/skills/speech-language-foundation-model/` に置いてあります。

初期状態は **mock** です。実音声認識も、音声言語基盤モデルも動きません。音声データは学習に使いません。

## 起動

```powershell
cd C:\devlop\SpeechLanguageFoundationModel
copy .env.example .env
docker compose up --build
```

| 役割 | URL |
|---|---|
| サービス画面 | http://127.0.0.1:8000/ |
| OpenAPI | http://127.0.0.1:8000/docs |
| Next.js（任意） | http://127.0.0.1:3000/ |
| PostgreSQL（ホスト） | `localhost:5440`（コンテナ内は 5432） |

ホストの 5432 は別プロセスが使っていることがあるため、この Compose は 5440 を開けます。

## テスト

```powershell
cd C:\devlop\SpeechLanguageFoundationModel
python -m pip install -r backend/requirements.txt pytest
pytest -q
.\.venv\Scripts\python scripts\load_smoke.py
```

`API_TOKEN` を `.env` に入れると、API は `X-Demo-Token`、WebSocket は `?token=` が必要になります。空なら認証しません。

## 実装状況

- 実装済: 録音断片の `/ws/live`、会話一覧と新規作成、任意のデモ用トークン、`/metrics`、起動時 ASR 暖機、会話往復、履歴と保存期間、監査、プロセス内回数制限、モック応答、確認音、Docker Compose、pytest
- 未実装: 実 Whisper の同梱、実時間の連続 ASR、HTTPS、本番の分散レート制限、ブラウザ自動 E2E
- 仮定は [`docs/10-assumptions.md`](docs/10-assumptions.md)

実音声認識を試す場合は `backend/requirements-asr.txt` を Dockerfile に入れ、`ASR_PROVIDER=whisper` を設定します。初回はモデル取得と CPU 処理に時間がかかります。精度は未計測です。
