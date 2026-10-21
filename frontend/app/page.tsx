'use client';

import {FormEvent, useEffect, useState} from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Transcript = {
  id: number;
  content: string;
  provider: string;
  created_at: string;
};

type Message = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<Transcript[]>([]);

  async function loadHistory() {
    const rows = await (await fetch(`${API}/api/transcripts`)).json();
    setHistory(rows);
  }

  async function loadThread(id: number) {
    const data = await (await fetch(`${API}/api/conversations/${id}`)).json();
    setMessages(data.messages || []);
  }

  useEffect(() => {
    loadHistory().catch(() => undefined);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', file);
      if (conversationId) form.append('conversation_id', String(conversationId));
      const r = await fetch(`${API}/api/turn`, {method: 'POST', body: form});
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || r.statusText);
      setConversationId(data.conversation_id);
      await loadThread(data.conversation_id);
      await loadHistory();
    } catch (err) {
      setMessages([{id: 0, role: 'assistant', content: `エラー: ${String(err)}`}]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>音声言語デモ</h1>
      <p>「会話する」で文字起こしと応答を一度に進めます。初期状態はモックです。</p>
      <p>{conversationId ? `会話 ID: ${conversationId}` : '会話はまだ始まっていません'}</p>
      <form onSubmit={submit}>
        <input
          aria-label="音声ファイル"
          type="file"
          accept="audio/*"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <button disabled={!file || busy} type="submit">
          {busy ? '処理中…' : '会話する'}
        </button>
        <button
          type="button"
          onClick={async () => {
            const data = await (await fetch(`${API}/api/conversations`, {method: 'POST'})).json();
            setConversationId(data.conversation_id);
            setMessages([]);
          }}
        >
          新しい会話
        </button>
      </form>
      <h2>会話</h2>
      {messages.map((msg) => (
        <pre key={msg.id} style={{whiteSpace: 'pre-wrap'}}>
          {msg.role === 'user' ? 'あなた' : '応答'}: {msg.content}
        </pre>
      ))}
      <h2>履歴</h2>
      <ul>
        {history.map((row) => (
          <li key={row.id}>
            {row.content}{' '}
            <button
              type="button"
              onClick={async () => {
                await fetch(`${API}/api/transcripts/${row.id}`, {method: 'DELETE'});
                await loadHistory();
              }}
            >
              削除
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
