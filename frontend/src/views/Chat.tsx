import { useEffect, useRef, useState } from 'react';
import { ago, del, errText, get, post } from '../api';
import { speech, useLoad, useNav, useSpeech } from '../hooks';
import { Badge, Btn, Card, Empty, Err, Modal, Field, inputCls, Spin, cx } from '../ui';

export default function Chat() {
  const { convId, go } = useNav();
  const { data: list, reload } = useLoad<any[]>('/conversations', undefined, 5000);
  const [creating, setCreating] = useState(false);
  return (
    <div className="flex h-full">
      <section className={cx('flex min-h-0 w-full flex-col border-zinc-800 md:w-80 md:shrink-0 md:border-r', convId != null && 'hidden md:flex')}>
        <div className="flex items-center justify-between border-b border-zinc-800 p-3"><h1 className="text-lg font-semibold">Chat</h1><Btn small kind="primary" onClick={() => setCreating(true)}>+ New</Btn></div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {(list || []).length === 0 && <Empty icon="✎" title="No conversations yet">Brainstorm, critique an idea, plan research, or review your week with the strategist.</Empty>}
          {(list || []).map(c => (
            <div key={c.id} role="button" tabIndex={0} onClick={() => go('chat', { convId: c.id })} onKeyDown={e => e.key === 'Enter' && go('chat', { convId: c.id })}
              className={cx('cursor-pointer border-b border-zinc-800/70 px-4 py-3 hover:bg-zinc-900', convId === c.id && 'bg-zinc-900')}>
              <div className="flex items-center gap-2"><span className="truncate text-sm font-medium">{c.title}</span>{c.off_record ? <Badge tone="amber">Off the record</Badge> : null}</div>
              <div className="truncate text-xs text-zinc-500">{c.mode} · {ago(c.updated)}</div><div className="truncate text-xs text-zinc-600">{c.preview}</div></div>))}
        </div>
      </section>
      <section className={cx('min-w-0 flex-1', convId == null && 'hidden md:block')}>
        {convId != null ? <Conversation id={convId} onBack={() => go('chat', { convId: null })} onChanged={reload} /> : <div className="hidden h-full items-center justify-center md:flex"><Empty icon="✎" title="Pick a conversation or start a new one" /></div>}
      </section>
      {creating && <NewConversation onClose={() => setCreating(false)} onCreated={id => { setCreating(false); reload(); go('chat', { convId: id }); }} />}
    </div>
  );
}

function NewConversation({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const { data: modes } = useLoad<any>('/chat/modes'); const { data: projs } = useLoad<any[]>('/projects'); const { projectId } = useNav();
  const [mode, setMode] = useState('brainstorm'); const [pid, setPid] = useState<string>(projectId ? String(projectId) : ''); const [off, setOff] = useState(false); const [err, setErr] = useState('');
  const go = async () => { try { const r = await post('/conversations', { mode, project_id: pid ? Number(pid) : null, off_record: off }); onCreated(r.id); } catch (e) { setErr(errText(e)); } };
  return (
    <Modal title="New conversation" onClose={onClose}>
      <div className="space-y-3">
        <div className="space-y-1.5">{Object.entries(modes || {}).map(([k, v]: any) => (
          <label key={k} className={cx('flex cursor-pointer items-start gap-2 rounded-lg border p-2.5', mode === k ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-800')}>
            <input type="radio" className="mt-1" checked={mode === k} onChange={() => setMode(k)} /><div><div className="text-sm font-medium">{v.name}</div><div className="text-xs text-zinc-500">{v.blurb}</div></div></label>))}</div>
        <Field label="Project (optional)" hint="The strategist can read the project’s state and record decisions and open questions."><select className={inputCls} value={pid} onChange={e => setPid(e.target.value)}><option value="">None</option>{(projs || []).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={off} onChange={e => setOff(e.target.checked)} /><span>Off the record <span className="block text-xs text-zinc-500">Stays on this device’s model, joins the graph on-device only, and is never quoted into other chats.</span></span></label>
        <Err>{err}</Err><div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" onClick={go}>Start</Btn></div>
      </div>
    </Modal>
  );
}

function Cite({ text, sources }: { text: string; sources: any[] }) {
  const { openArticle } = useNav();
  const parts = text.split(/(\[R\d+\])/g);
  return <>{parts.map((p, i) => { const m = p.match(/^\[R(\d+)\]$/); const s = m && sources?.find(x => x.n === Number(m[1]));
    return s ? <button key={i} className="mx-0.5 rounded bg-indigo-900/60 px-1 text-xs text-indigo-200 hover:bg-indigo-800" title={s.title} onClick={() => openArticle(s.article_id)}>{p}</button> : <span key={i}>{p}</span>; })}</>;
}

function Conversation({ id, onBack, onChanged }: { id: number; onBack: () => void; onChanged: () => void }) {
  const { data: c, reload } = useLoad<any>(`/conversations/${id}`, undefined, 900);
  const { go } = useNav(); const sp = useSpeech();
  const [text, setText] = useState(''); const [err, setErr] = useState(''); const end = useRef<HTMLDivElement>(null);
  const { data: st } = useLoad<any>('/status');
  const running = c?.status === 'running';
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [c?.messages?.length, c?.messages?.[c?.messages?.length - 1]?.content]);
  const send = async () => { const t = text.trim(); if (!t) return; setText(''); setErr(''); try { await post(`/conversations/${id}/send`, { text: t }); reload(); onChanged(); } catch (e) { setErr(errText(e)); setText(t); } };
  const decide = async (aid: string, approved: boolean) => { try { await post(`/approvals/${aid}`, { approved }); reload(); } catch (e) { setErr(errText(e)); } };
  if (!c) return <div className="p-6"><Spin /></div>;
  const pending = (c.approvals || []).filter((a: any) => a.status === 'pending');
  const msgs: any[] = c.messages || [];
  const noKey = !st?.preflight?.ollama && String(st?.model || '').startsWith('ollama');
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-zinc-800 p-3"><button className="text-sm text-zinc-400 md:hidden" onClick={onBack}>←</button>
        <div className="min-w-0 flex-1"><div className="truncate font-medium">{c.title}</div><div className="text-xs text-zinc-500">{c.mode}{c.off_record ? ' · off the record' : ''}</div></div>
        <Btn small kind="ghost" onClick={async () => { if (confirm('Delete this conversation?')) { await del(`/conversations/${id}`); onChanged(); onBack(); } }}>Delete</Btn></div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" role="log" aria-live="polite">
        {noKey && <Err>Ollama isn’t reachable, so the strategist can’t answer. Start it with <code>ollama serve</code>.</Err>}
        {msgs.length === 0 && <Card className="text-sm text-zinc-400"><div className="mb-1 font-medium text-zinc-200">{c.blurb}</div>Ask anything. Answers cite your library as [R1], [R2]… and the strategist can search it, explore the graph, and — only after you approve — read a page or follow a source.</Card>}
        {msgs.map((m: any) => (
          <div key={m.id} className={cx('max-w-[85%] rounded-xl px-3.5 py-2.5', m.role === 'user' ? 'ml-auto bg-indigo-600' : 'mr-auto bg-zinc-800')} aria-label={`${m.role === 'user' ? 'You' : 'Strategist'} said`}>
            <div className="whitespace-pre-wrap text-sm leading-relaxed">{m.role === 'assistant' ? <Cite text={m.content || '…'} sources={m.meta?.sources || []} /> : m.content}{m.meta?.streaming && m.id === msgs[msgs.length - 1].id && running && <span className="ml-1 animate-pulse">▍</span>}</div>
            {m.meta?.tools?.length > 0 && <div className="mt-2 space-y-0.5 text-[11px] text-zinc-400">{m.meta.tools.map((t: any, i: number) => <div key={i}>🛠 {t.tool}{t.args?.url ? ` ${t.args.url}` : ''}{t.auto ? ' (auto-approved)' : t.approved === false ? ' (declined)' : ''}</div>)}</div>}
            {m.role === 'assistant' && m.meta?.sources?.length > 0 && <details className="mt-2 text-xs text-zinc-400"><summary className="cursor-pointer">Sources ({m.meta.sources.length})</summary><ul className="mt-1 space-y-1">{m.meta.sources.map((s: any) => <li key={s.n}>[R{s.n}] <button className="text-indigo-300 hover:underline" onClick={() => go('reading', { articleId: s.article_id })}>{s.title}</button> <span className="text-zinc-500">— {s.why}</span></li>)}</ul></details>}
            {m.role === 'assistant' && m.content && speech.supported && !m.meta?.streaming && <button className="mt-1 text-[11px] text-zinc-500 hover:text-zinc-300" onClick={() => speech.speak([m.content.replace(/\[R\d+\]/g, '')])}>🔊 Read</button>}
          </div>))}
        {running && msgs[msgs.length - 1]?.role === 'user' && <div className="text-xs italic text-zinc-500"><Spin /> Strategist is thinking…</div>}
        <div ref={end} />
      </div>
      {pending.map((a: any) => (
        <div key={a.id} className="border-t border-amber-700/50 bg-amber-950/30 p-3"><div className="mb-1 text-sm font-medium text-amber-200">Approval needed · {a.title}</div><div className="mb-2 break-all text-sm text-zinc-300">{a.detail}</div>
          <div className="flex gap-2"><Btn kind="primary" small onClick={() => decide(a.id, true)}>Approve</Btn><Btn small onClick={() => decide(a.id, false)}>Decline</Btn></div></div>))}
      <div className="border-t border-zinc-800 p-3"><Err>{err}</Err>
        <form onSubmit={e => { e.preventDefault(); send(); }} className="flex gap-2"><input value={text} onChange={e => setText(e.target.value)} disabled={running && pending.length > 0} placeholder={running ? 'Strategist is answering…' : 'Message the strategist'} aria-label="Message" className="flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm outline-none focus:border-indigo-500" />
          <Btn type="submit" kind="primary" disabled={!text.trim() || running}>Send</Btn></form></div>
    </div>
  );
}
