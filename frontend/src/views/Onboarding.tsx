import { useState } from 'react';
import { post, errText } from '../api';
import { Btn, Card, Err, Field, inputCls, Badge, Spin } from '../ui';

export default function Onboarding({ status, onDone }: { status: any; onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [notes, setNotes] = useState(''); const [links, setLinks] = useState('');
  const [prop, setProp] = useState<any>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const [skip, setSkip] = useState<Record<string, boolean>>({});
  const pre = status.preflight || {};

  const propose = async () => {
    setBusy(true); setErr('');
    try { setProp(await post('/onboarding/propose', { notes: notes + '\n\nLinks:\n' + links })); setStep(2); }
    catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  const manual = () => { setProp({ interests: notes, projects: [], sources: [] }); setStep(2); };
  const apply = async () => {
    setBusy(true); setErr('');
    try {
      const body = { ...prop, sources: prop.sources.filter((_: any, i: number) => !skip['s' + i]), projects: prop.projects.filter((_: any, i: number) => !skip['p' + i]) };
      const r = await post('/onboarding/apply', body);
      if (r.errors?.length) { setErr('Some sources couldn’t be added: ' + r.errors.join('; ')); }
      onDone();
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  const upd = (path: 'projects' | 'sources', i: number, k: string, v: string) => setProp({ ...prop, [path]: prop[path].map((x: any, j: number) => j === i ? { ...x, [k]: v } : x) });

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto p-6">
      <div className="w-full max-w-2xl space-y-4 py-6">
        <div className="text-center"><div className="text-2xl font-semibold">Welcome to SmartWard</div>
          <div className="mt-1 text-sm text-zinc-400">A local-first research strategist. It reads the AI and software world for you, links what you read with what you discuss, and keeps it all on this laptop.</div></div>
        <div className="flex justify-center gap-2 text-xs text-zinc-500">{['Check', 'Tell me', 'Review'].map((s, i) => <span key={s} className={i === step ? 'text-indigo-300' : ''}>{i + 1}. {s}</span>)}</div>

        {step === 0 && (<Card className="space-y-3">
          <div className="font-medium">Before we start</div>
          <ul className="space-y-1.5 text-sm">
            <li>{pre.ollama ? '✅' : '❌'} Ollama is running {!pre.ollama && <span className="text-zinc-500">— start it with <code className="rounded bg-zinc-800 px-1">ollama serve</code></span>}</li>
            <li>{pre.chat_model ? '✅' : '❌'} Chat model <Badge>{status.model}</Badge> {!pre.chat_model && <span className="text-zinc-500">— run <code className="rounded bg-zinc-800 px-1">ollama pull llama3.2:3b</code></span>}</li>
            <li>{pre.embed_model ? '✅' : '⚠️'} Embedding model for search {!pre.embed_model && <span className="text-zinc-500">— run <code className="rounded bg-zinc-800 px-1">ollama pull nomic-embed-text</code> (search falls back to keywords without it)</span>}</li>
          </ul>
          <div className="text-xs text-zinc-500">Everything runs on this machine. Nothing is sent to a cloud model unless you add a provider in Settings.</div>
          <div className="flex justify-end"><Btn kind="primary" onClick={() => setStep(1)}>Continue</Btn></div></Card>)}

        {step === 1 && (<Card className="space-y-3">
          <Field label="What do you follow, and what are you working on?" hint="Topics, tools, projects, anything. One or two sentences is plenty."><textarea className={inputCls} rows={5} value={notes} onChange={e => setNotes(e.target.value)} placeholder="e.g. LLM inference and serving, local models, agent frameworks. Building a home-lab inference stack with vLLM." /></Field>
          <Field label="Any links to follow? (optional)" hint="Blogs, feeds, GitHub repos — one per line."><textarea className={inputCls} rows={3} value={links} onChange={e => setLinks(e.target.value)} placeholder="https://github.com/vllm-project/vllm" /></Field>
          <Err>{err}</Err>
          <div className="flex justify-between"><Btn kind="ghost" onClick={() => setStep(0)}>Back</Btn>
            <div className="flex gap-2"><Btn onClick={manual} disabled={!notes.trim()}>Set up by hand</Btn><Btn kind="primary" onClick={propose} disabled={busy || !notes.trim()}>{busy ? <><Spin /> Thinking…</> : 'Propose a setup'}</Btn></div></div></Card>)}

        {step === 2 && prop && (<div className="space-y-3">
          <Card className="space-y-3"><Field label="Your interests (used to decide what's relevant)"><textarea className={inputCls} rows={3} value={prop.interests} onChange={e => setProp({ ...prop, interests: e.target.value })} /></Field></Card>
          <Card className="space-y-2"><div className="font-medium">Projects</div>
            {prop.projects.length === 0 && <div className="text-sm text-zinc-500">None proposed. You can add projects later.</div>}
            {prop.projects.map((p: any, i: number) => (<div key={i} className="flex items-start gap-2"><input type="checkbox" checked={!skip['p' + i]} onChange={e => setSkip({ ...skip, ['p' + i]: !e.target.checked })} className="mt-3" />
              <div className="flex-1 space-y-1"><input className={inputCls} value={p.name} onChange={e => upd('projects', i, 'name', e.target.value)} /><input className={inputCls} value={p.goal || ''} onChange={e => upd('projects', i, 'goal', e.target.value)} placeholder="Goal" /></div></div>))}</Card>
          <Card className="space-y-2"><div className="font-medium">Sources to follow</div>
            {prop.sources.length === 0 && <div className="text-sm text-zinc-500">None proposed. Add sources from the Reading tab.</div>}
            {prop.sources.map((s: any, i: number) => (<div key={i} className="flex items-center gap-2"><input type="checkbox" checked={!skip['s' + i]} onChange={e => setSkip({ ...skip, ['s' + i]: !e.target.checked })} />
              <Badge tone="indigo">{s.kind}</Badge><input className={inputCls} value={s.url || s.query || ''} onChange={e => upd('sources', i, s.url ? 'url' : 'query', e.target.value)} /></div>))}
            <div className="text-xs text-zinc-500">Nothing is fetched until you finish. Each source is checked first, and any that fail are reported.</div></Card>
          <Err>{err}</Err>
          <div className="flex justify-between"><Btn kind="ghost" onClick={() => setStep(1)}>Back</Btn><Btn kind="primary" onClick={apply} disabled={busy}>{busy ? <><Spin /> Setting up…</> : 'Create and start reading'}</Btn></div></div>)}
      </div>
    </div>
  );
}
