# Speech Language Foundation Model Skill

Claude Code向けSkillと、FastAPI + Next.js + PostgreSQLの最小実行サンプルです。

## Claude Codeへの登録
このディレクトリをプロジェクトの `.claude/skills/speech-language-foundation-model/` に配置してください。`SKILL.md` のfrontmatter nameとフォルダ名は一致します。Claude Codeに「音声言語基盤モデルSkillを使って音声認識機能を追加して」と依頼します。

## 起動
```bash
docker compose up --build
```
- UI: http://localhost:3000
- API仕様: http://localhost:8000/docs
- ヘルスチェック: http://localhost:8000/health

初期状態は **mock** モードで、実際の音声認識はしません。実音声認識を使うには `backend/requirements-asr.txt` の依存関係をDockerfileに導入し、`ASR_PROVIDER=whisper` を設定してください。Whisperモデルの初回取得にネットワークが必要です。CPU処理には時間がかかります。

## 実装状況
- 実装済: 音声ファイルアップロード、サイズ/MIME検査、文字起こしProviderの切替、履歴DB保存、UI、Docker Compose
- 設計ガイドのみ: LLM対話、TTS、リアルタイムWebSocket、認証、監査、保存期間制御、E2E
- このサンプルは開発用です。本番運用には認証・認可、音声内容検査、データ削除、レート制限、HTTPS、モデルの再利用、接続情報の秘匿が必要です。

## 追加開発の推奨順
1. ASRモデルを起動時に一度だけロードして性能改善
2. LLM Providerと対話APIを追加
3. TTS Providerと音声再生UIを追加
4. 録音UIとWebSocketストリーミング
5. 認証、データ保存期限、監査ログ、負荷テスト
