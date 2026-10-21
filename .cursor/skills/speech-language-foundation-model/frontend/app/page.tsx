'use client';
import {useState, type FormEvent} from 'react';
export default function Home(){
 const [file,setFile]=useState<File|null>(null);const [result,setResult]=useState('');const [busy,setBusy]=useState(false);
 async function submit(e:FormEvent){e.preventDefault();if(!file)return;setBusy(true);setResult('');try{const form=new FormData();form.append('file',file);const r=await fetch(`${process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'}/api/transcribe`,{method:'POST',body:form});const data=await r.json();if(!r.ok)throw new Error(JSON.stringify(data));setResult(data.transcript);}catch(e){setResult(`エラー: ${String(e)}`)}finally{setBusy(false)}}
 return <main><h1>音声言語基盤モデル デモ</h1><p>音声ファイルをアップロードして文字起こしします。</p><form onSubmit={submit}><input aria-label="音声ファイル" type="file" accept="audio/*" onChange={e=>setFile(e.target.files?.[0]||null)}/><button disabled={!file||busy} type="submit">{busy?'処理中…':'文字起こし'}</button></form><h2>結果</h2><pre style={{whiteSpace:'pre-wrap'}}>{result||'結果はここに表示されます'}</pre></main>
}
