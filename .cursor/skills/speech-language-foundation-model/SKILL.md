---
name: speech-language-foundation-model
description: Python FastAPI、Next.js、React、TypeScript、PostgreSQLを使った音声認識・音声対話・音声合成システムの設計、実装、テスト、Docker運用を支援する。
---
# Speech Language Foundation Model Skill

## 起動条件
音声認識、文字起こし、音声合成、音声対話、音声LLM、音声言語基盤モデル、ASR/TTSの開発を依頼された場合に利用する。

## 技術構成
- Backend: Python 3.12, FastAPI, SQLAlchemy, psycopg
- Frontend: Next.js App Router, React, TypeScript
- DB: PostgreSQL 16
- ASR: faster-whisper（任意インストール）
- LLM/TTS: Provider抽象化。外部サービスを接続するまでモックを使用
- Docker Compose, pytest

## 開発手順
1. 音声形式、言語、遅延、個人情報の要件を確認する。
2. ASR / LLM / TTSのプロバイダーを選定し、機密データの外部送信を確認する。
3. FastAPIで音声入力、文字起こし、応答生成APIを設計する。
4. PostgreSQLで履歴を管理し、保存期間と削除APIを用意する。
5. Next.jsで録音、アップロード、結果表示UIを実装する。
6. pytestとブラウザE2Eテストを実行する。
7. Docker Composeで動作確認し、運用監視・認証・レート制限を追加する。

## セキュリティ規約
- 秘密情報をコードに埋め込まない。
- 音声ファイルのサイズ、形式、保存期間を制限する。
- 本番公開前に認証・認可、HTTPS、マルウェア検査、監査ログ、削除機能を実装する。
- 音声データのモデル学習利用可否を明示する。

## 完了条件
APIとUIの動作、DB接続、失敗時のエラー処理、README、テスト手順を確認する。
