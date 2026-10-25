import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { ago, del, errText, get, post } from '../api';
import { speech, useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Empty, Err, Modal, Field, inputCls, Spin, cx } from '../ui';
import { ask, toast } from '../feedback';
import { useHandsFree } from '../useHandsFree';
import { wantAudioChat } from '../voiceIntent';
import { Mic } from 'lucide-react';

export default function Chat() {
  const { convId, go } = useNav();
  const { data: list, reload } = useLoad<any[]>('/conversations', undefined, 5000);
  const [creating, setCreating] = useState(false);
  return (
    <div className="flex h-full">
      <section className={cx('flex min-h-0 w-full flex-col border-zinc-800 md:w-80 md:shrink-0 md:border-r', convId != null && 'hidden md:flex')}>
        <div className="flex items-center justify-between border-b border-zinc-800 p-3"><h1 className="text-lg font-semibold">Chat</h1><div className="flex gap-1.5"><Btn small title="Start a new chat and just talk: it listens and reads the answers aloud" onClick={async () => { try { const r = await post('/conversations', { mode: 'brainstorm' }); wantAudioChat(); reload(); go('chat', { convId: r.id }); } catch (e) { toast.error(errText(e)); } }}><Mic size={13} aria-hidden /> Talk</Btn><Btn small kind="primary" onClick={() => setCreating(true)}>+ New</Btn></div></div>
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

/** Your own message; a long one (an article you sent over) is folded to a few lines. */
function UserText({ text }: { text: string }) {
  const [more, setMore] = useState(false); const long = text.length > 400;
  return <div className="text-sm leading-relaxed"><div className={cx('whitespace-pre-wrap', long && !more && 'line-clamp-4')}>{text}</div>
    {long && <button className="mt-1 text-xs underline opacity-80" onClick={() => setMore(!more)}>{more ? 'Show less' : 'Show more'}</button>}</div>;
}

/** Markdown from the model, sanitized; [R3] becomes a link to source 3. */
function Rich({ text, sources }: { text: string; sources: any[] }) {
  const { openArticle } = useNav();
  const md = text.replace(/\[R(\d+)\]/g, (_m, n) => `[R${n}](#cite-${n})`);
  return (
    <div className="md-body text-sm leading-relaxed">
      <ReactMarkdown rehypePlugins={[rehypeSanitize]} components={{
        a: ({ href, children }) => {
          const m = href?.match(/^#cite-(\d+)$/); const s = m && sources?.find(x => x.n === Number(m[1]));
          if (m) return s
            ? <button className="mx-0.5 rounded bg-indigo-900/60 px-1 text-xs text-indigo-200 hover:bg-indigo-800" title={s.title} onClick={() => openArticle(s.article_id)}>{children}</button>
            : <span className="text-xs text-zinc-500">{children}</span>;
          return <a href={href} target="_blank" rel="noreferrer noopener" className="text-indigo-300 underline">{children}</a>;
        },
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-2 list-disc pl-5">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 list-decimal pl-5">{children}</ol>,
        code: ({ children }) => <code className="rounded bg-black/30 px-1 text-[0.85em]">{children}</code>,
        pre: ({ children }) => <pre className="mb-2 overflow-x-auto rounded bg-black/30 p-2 text-xs">{children}</pre>,
      }}>{md}</ReactMarkdown>
    </div>
  );
}

function Conversation({ id, onBack, onChanged }: { id: number; onBack: () => void; onChanged: () => void }) {
  const [fast, setFast] = useState(false);
  const { data: c, reload } = useLoad<any>(`/conversations/${id}`, undefined, fast ? 900 : 5000);
  const { go } = useNav();
  const [text, setText] = useState(''); const [err, setErr] = useState(''); const end = useRef<HTMLDivElement>(null);
  const { data: st } = useLoad<any>('/status');
  const running = c?.status === 'running';
  useEffect(() => { setFast(!!running); }, [running]);
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [c?.messages?.length, c?.messages?.[c?.messages?.length - 1]?.content]);
  const sendText = async (t: string) => { if (!t) return; setText(''); setErr(''); setFast(true); try { await post(`/conversations/${id}/send`, { text: t }); reload(); onChanged(); } catch (e) { setErr(errText(e)); setText(t); } };
  const send = () => sendText(text.trim());
  const stop = async () => { try { await post(`/conversations/${id}/cancel`); toast.info('Stopping…'); reload(); } catch (e) { setErr(errText(e)); } };
  const decide = async (aid: string, approved: boolean) => { try { await post(`/approvals/${aid}`, { approved }); reload(); } catch (e) { setErr(errText(e)); } };
  const copy = async (t: string) => { try { await navigator.clipboard.writeText(t); toast.ok('Copied'); } catch { toast.error('Couldn’t copy'); } };
  const pendingNow = (c?.approvals || []).filter((x: any) => x.status === 'pending');
  const hf = useHandsFree({ running: !!running, messages: c?.messages || [], pending: pendingNow, send: sendText, stop, decide });
  if (!c) return <div className="p-6"><Spin /></div>;
  const pending = (c.approvals || []).filter((a: any) => a.status === 'pending');
  const msgs: any[] = c.messages || [];
  const ollamaDown = !st?.preflight?.ollama && String(st?.model || '').startsWith('ollama');
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-zinc-800 p-3"><button className="text-sm text-zinc-400 md:hidden" aria-label="Back to conversations" onClick={onBack}>←</button>
        <div className="min-w-0 flex-1"><div className="truncate font-medium">{c.title}</div><div className="text-xs text-zinc-500">{c.mode}{c.off_record ? ' · off the record' : ''}</div></div>
        <button type="button" role="switch" aria-checked={hf.on} onClick={hf.toggle} title={hf.on ? 'Audio chat is on: turn it off (or say “stop listening”)' : 'Audio chat: talk to the strategist and hear its answers'}
          className={cx('inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium', hf.on ? 'border-red-500 bg-red-950/40 text-red-300' : 'border-zinc-700 text-zinc-300 hover:bg-zinc-800')}>
          <span className={cx('relative h-4 w-7 rounded-full transition-colors', hf.on ? 'bg-red-500' : 'bg-zinc-600')} aria-hidden><span className={cx('absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all', hf.on ? 'left-3.5' : 'left-0.5')} /></span>
          <Mic size={13} aria-hidden /> Audio chat</button>
        <Btn small kind="ghost" onClick={async () => { if (await ask.confirm({ title: 'Delete this conversation?', body: 'The messages are removed. Anything you saved to a project stays.', confirmLabel: 'Delete', danger: true })) { await del(`/conversations/${id}`); onChanged(); onBack(); } }}>Delete</Btn></div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" role="log" aria-live="polite">
        {ollamaDown && <Err>Ollama isn’t reachable, so the strategist can’t answer. Start it with <code>ollama serve</code>.</Err>}
        {msgs.length === 0 && <Card className="text-sm text-zinc-400"><div className="mb-1 font-medium text-zinc-200">{c.blurb}</div>Ask anything. Answers cite your library as [R1], [R2]… and the strategist can search it, explore the graph, and — only after you approve — read a page or follow a source.</Card>}
        {msgs.map((m: any) => (
          <div key={m.id} className={cx('group max-w-[85%] rounded-xl px-3.5 py-2.5', m.role === 'user' ? 'ml-auto bg-indigo-600' : 'mr-auto bg-zinc-800')} aria-label={`${m.role === 'user' ? 'You' : 'Strategist'} said`}>
            {m.role === 'assistant' ? <Rich text={m.content || '…'} sources={m.meta?.sources || []} /> : <UserText text={m.content} />}
            {m.meta?.streaming && m.id === msgs[msgs.length - 1].id && running && <span className="ml-1 animate-pulse">▍</span>}
            {m.meta?.tools?.length > 0 && <div className="mt-2 space-y-0.5 text-[11px] text-zinc-400">{m.meta.tools.map((t: any, i: number) => <div key={i}>🛠 {t.tool}{t.args?.url ? ` ${t.args.url}` : ''}{t.auto ? ' (auto-approved)' : t.approved === false ? ' (declined)' : ''}</div>)}</div>}
            {m.role === 'assistant' && m.meta?.sources?.length > 0 && <details className="mt-2 text-xs text-zinc-400"><summary className="cursor-pointer">Sources ({m.meta.sources.length})</summary><ul className="mt-1 space-y-1">{m.meta.sources.map((s: any) => <li key={s.n}>[R{s.n}] <button className="text-indigo-300 hover:underline" onClick={() => go('reading', { articleId: s.article_id })}>{s.title}</button> <span className="text-zinc-500">— {s.why}</span></li>)}</ul></details>}
            <div className="mt-1 flex items-center gap-3 text-[11px] text-zinc-500">
              {m.ts ? <time dateTime={new Date(m.ts * 1000).toISOString()} title={new Date(m.ts * 1000).toLocaleString()}>{ago(m.ts)}</time> : null}
              {m.role === 'assistant' && m.content && !m.meta?.streaming && <>
                <button className="hover:text-zinc-300 focus:text-zinc-300" onClick={() => copy(m.content)}>Copy</button>
                {speech.supported && <button className="hover:text-zinc-300 focus:text-zinc-300" onClick={() => speech.speak([m.content.replace(/\[R\d+\]/g, '')])}>🔊 Read</button>}
              </>}
              {m.meta?.cancelled && <span>stopped</span>}
            </div>
          </div>))}
        {running && msgs[msgs.length - 1]?.role === 'user' && <div className="text-xs italic text-zinc-500"><Spin /> Strategist is thinking…</div>}
        <div ref={end} />
      </div>
      {pending.map((a: any) => (
        <div key={a.id} className="border-t border-amber-700/50 bg-amber-950/30 p-3"><div className="mb-1 text-sm font-medium text-amber-200">Approval needed · {a.title}</div><div className="mb-2 break-all text-sm text-zinc-300">{a.detail}</div>
          <div className="flex gap-2"><Btn kind="primary" small onClick={() => decide(a.id, true)}>Approve</Btn><Btn small onClick={() => decide(a.id, false)}>Decline</Btn></div></div>))}
      <div className="border-t border-zinc-800 p-3"><Err>{err || hf.error}</Err>
        {hf.on && <div className="mb-2 flex items-center gap-2 text-xs text-zinc-400" role="status" aria-live="polite"><span className="h-2 w-2 animate-pulse rounded-full bg-red-500" aria-hidden />
          {{ loading: 'Loading the speech model…', listening: 'Listening… just talk. Say “stop listening” or use the switch to finish.', hearing: 'Hearing you…', thinking: 'Thinking…', speaking: 'Speaking… (the microphone is paused so it doesn’t hear itself)', off: '' }[hf.status]}
          {pending.length > 0 && ' · Say “approve” or “decline”.'}
          {hf.status === 'speaking' && <button type="button" className="ml-auto rounded border border-zinc-700 px-2 py-0.5 hover:bg-zinc-800" onClick={() => speech.stop()}>Stop talking</button>}</div>}
        <form onSubmit={e => { e.preventDefault(); send(); }} className="flex items-end gap-2">
          <textarea rows={Math.min(6, Math.max(1, text.split('\n').length))} value={text} onChange={e => setText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (!running) send(); } }}
            disabled={running && pending.length > 0} placeholder={running ? 'Strategist is answering…' : 'Message the strategist (Shift+Enter for a new line)'} aria-label="Message"
            className="flex-1 resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm outline-none focus:border-indigo-500" />
          {running ? <Btn onClick={stop} kind="danger">Stop</Btn> : <Btn type="submit" kind="primary" disabled={!text.trim()}>Send</Btn>}
        </form></div>
    </div>
  );
}
