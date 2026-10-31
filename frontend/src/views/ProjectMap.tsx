import { useEffect, useRef, useState } from 'react';
import { errText, post, put } from '../api';
import { onPhone } from '../device';
import { toast } from '../feedback';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Err, inputCls } from '../ui';
import { TestThis } from './Bench';

const TONE: Record<string, [string, 'red' | 'green' | 'indigo' | 'zinc']> = { threatens: ['Could undercut', 'red'], accelerates: ['Could speed up', 'green'], enables: ['Could open up', 'indigo'], news: ['Recent news', 'zinc'], quiet: ['Quiet', 'zinc'] };
const TYPES: [string, string, string][] = [['actor', '⬭', 'people / outside systems'], ['app', '▢', 'applications'], ['agent', '⬡', 'agents'], ['service', '▭', 'platform services'],
  ['gateway', '⏢', 'gateways, routers'], ['datastore', '⛁', 'data stores'], ['model', '▥', 'models you run'], ['external', '⏵', 'cloud APIs'], ['infra', '▱', 'infrastructure']];
const EXAMPLE = `@pattern llm_serving

Users (actor): developers
API gateway (gateway): api gateway, load balancer
Scheduler (service): continuous batching, scheduler

[On-prem data center]
vLLM server (model): vllm, paged attention
KV cache (datastore): kv cache, prefix caching
GPUs (infra): h100, gpu

Users -> API gateway: send prompts (OpenAI API)
API gateway -> Scheduler: queues requests
Scheduler -> vLLM server: batches
vLLM server -> KV cache: reads and writes
vLLM server -> GPUs: runs on
`;
let seq = 0;

/** Draws Mermaid source into an element. Mermaid loads only when a map is shown; strict mode means diagram text can never run scripts. */
async function draw(el: HTMLElement, src: string, onPick: (id: string) => void, fit = false) {
  const { default: mermaid } = await import('mermaid');
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: document.documentElement.dataset.theme === 'light' ? 'default' : 'dark', flowchart: { htmlLabels: false, curve: 'basis' } });
  const { svg } = await mermaid.render(`project-map-${++seq}`, src);
  el.innerHTML = svg;
  const s = el.querySelector('svg');
  if (s && !fit) { s.style.maxWidth = 'none'; s.style.width = (s.viewBox?.baseVal?.width || s.getBoundingClientRect().width) + 'px'; }     // full size: readable labels, scroll sideways
  el.querySelectorAll<SVGGElement>('g.node').forEach(g => {
    const id = /flowchart-(c\d+)-/.exec(g.id)?.[1]; if (!id) return;
    g.style.cursor = 'pointer'; g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button');
    g.addEventListener('click', () => onPick(id)); g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick(id); } });
  });
}

/** What a reviewer would say about the map: missing parts for its pattern, loose ends, unlabelled connections. */
function Checks({ checks, open }: { checks: any[]; open?: boolean }) {
  if (!checks?.length) return <p className="text-xs text-emerald-400">No review notes: every expected part is there and everything is connected and labelled.</p>;
  const warns = checks.filter(c => c.level === 'warn').length;
  return (
    <details open={open} className="text-xs"><summary className="cursor-pointer text-zinc-400">Review notes: {warns} to fix, {checks.length - warns} to consider</summary>
      <ul className="mt-1 space-y-0.5">{checks.map((c, i) => <li key={i} className={c.level === 'warn' ? 'text-amber-300' : 'text-zinc-400'}>{c.level === 'warn' ? '⚠ ' : '· '}{c.text}</li>)}</ul></details>
  );
}

/** Per part: how many recent developments its words match, and each word's own count, so words nobody uses stand out while you type. */
function Matches({ map }: { map: any }) {
  return (
    <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-left text-zinc-500"><th className="py-1 pr-2 font-normal">Part</th><th className="pr-2 font-normal">Matches</th><th className="font-normal">Words (matches each)</th></tr></thead>
      <tbody>{map.parts.map((p: any) => { const o = map.overlay[p.id] || {}; return (
        <tr key={p.id} className="border-t border-zinc-800 align-top"><td className="py-1 pr-2">{p.suggested && <span title="Suggested by SmartWard">~</span>}{p.label} <span className="text-zinc-500">{p.type}{p.zone ? ` · ${p.zone}` : ''}</span></td>
          <td className={'pr-2 ' + (o.development_count ? 'text-zinc-200' : 'text-amber-300')}>{o.development_count || 0}</td>
          <td>{Object.entries(o.terms || {}).map(([t, n]: any) => <span key={t} className={'mr-2 ' + (n ? 'text-zinc-300' : 'text-amber-300/80')}>{t} {n}</span>)}</td></tr>); })}</tbody></table></div>
  );
}

/** The project's architecture as a diagram, with recent developments and implications placed on the part they mention. */
export default function ProjectMap({ pid }: { pid: number }) {
  const { data, reload } = useLoad<any>(`/projects/${pid}/map`);
  const { openArticle } = useNav();
  const [editing, setEditing] = useState<string | null>(null); const [preview, setPreview] = useState<any>(null); const [draftNote, setDraftNote] = useState('');
  const [picked, setPicked] = useState<string | null>(null); const [busy, setBusy] = useState(''); const [err, setErr] = useState(''); const [fit, setFit] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const map = editing !== null ? preview : data?.map;

  useEffect(() => {                                 // while editing, redraw and recount from the lines as you type (nothing is saved)
    if (editing === null) return;
    const t = setTimeout(() => post(`/projects/${pid}/map/preview`, { text: editing }).then(setPreview).catch(() => {}), 400);
    return () => clearTimeout(t);
  }, [editing, pid]);
  useEffect(() => {
    if (!box.current || !map?.parts?.length) { if (box.current) box.current.innerHTML = ''; return; }
    draw(box.current, map.mermaid, setPicked, fit).catch(e => setErr('Couldn’t draw the map: ' + (e?.message || e)));
  }, [map?.mermaid, fit]);

  const draft = async () => {
    setBusy('draft'); setErr(''); setDraftNote('');
    try {
      const d = await post(`/projects/${pid}/map/draft`); setEditing(d.text); setPicked(null);
      setDraftNote(`Drafted with ${d.model.replace(/^openrouter\//, '')}${d.pattern ? `, checked against the ${d.pattern.replace('_', ' ')} pattern` : ''}${d.revised ? ' and revised once to fix what the checks found' : ''}. Dashed parts are suggestions: keep or delete them, then Save.`);
    } catch (e) { setErr(errText(e)); }
    setBusy('');
  };
  const save = async () => { setBusy('save'); setErr(''); try { await put(`/projects/${pid}/map`, { text: editing }); setEditing(null); setPreview(null); setDraftNote(''); reload(); } catch (e) { setErr(errText(e)); } setBusy(''); };
  const download = () => {
    const svg = box.current?.querySelector('svg'); if (!svg) return;
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([svg.outerHTML], { type: 'image/svg+xml' })); a.download = 'architecture.svg'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  };
  const part = map?.parts?.find((c: any) => c.id === picked); const over = picked ? map?.overlay?.[picked] : null;
  const label = (id: string) => map?.parts?.find((c: any) => c.id === id)?.label || id;
  const links = part ? map.edges.filter((e: any) => e.a === part.id || e.b === part.id) : [];

  return (
    <Card className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-medium">Architecture</h2>
        <div className="text-xs text-zinc-500">The project’s parts, where they run and what flows between them, with recent developments and implications placed on the part they mention. Click a part.</div></div>
        {!onPhone && editing === null && <div className="flex flex-wrap gap-2">
          {data?.map && <><Btn small onClick={download}>⤓ SVG</Btn><Btn small onClick={draft} loading={busy === 'draft'}>Redraft</Btn><Btn small onClick={() => { setEditing(data.map.text); setPicked(null); }}>Edit</Btn></>}
          {!data?.map && <><Btn small kind="primary" onClick={draft} loading={busy === 'draft'}>Draft it for me</Btn><Btn small onClick={() => setEditing(EXAMPLE)}>Write it myself</Btn></>}</div>}
      </div>
      <Err>{err}</Err>
      {busy === 'draft' && <p className="text-xs text-zinc-400" role="status">Drafting, checking it against a reference architecture, and revising once if needed. This can take a minute or two.</p>}
      {editing !== null && <div className="space-y-2">
        {draftNote && <p className="text-xs text-indigo-300">{draftNote}</p>}
        <textarea className={inputCls + ' h-56 font-mono text-xs'} value={editing} onChange={e => setEditing(e.target.value)} aria-label="Architecture lines" spellCheck={false} />
        <details className="text-xs text-zinc-500"><summary className="cursor-pointer">How to write it</summary>
          <ul className="mt-1 space-y-0.5"><li><code>Name (type): words, articles, use</code> a part. Types: {TYPES.map(([t, s, d]) => <span key={t} className="mr-2" title={d}>{s} <code>{t}</code></span>)}</li>
            <li><code>[On-prem data center]</code> parts below it run there, until the next <code>[zone]</code>; <code>[]</code> ends it.</li>
            <li><code>A -&gt; B: what flows (protocol)</code> requests or data; <code>A =&gt; B: deploys</code> control.</li>
            <li><code>~Name …  # why</code> a suggested part, drawn dashed; <code>@pattern agent_platform</code> checks it against a reference (agent_platform, llm_serving, rag, hybrid_routing, none).</li>
            <li>Words match whole words in recent developments; plurals and hyphens are allowed. Amber numbers are words no article uses yet.</li></ul></details>
        {preview?.problems?.length > 0 && <ul className="text-xs text-red-300">{preview.problems.map((p: string) => <li key={p}>{p}</li>)}</ul>}
        {preview && <Checks checks={preview.checks} open />}
        {preview?.parts?.length > 0 && <Matches map={preview} />}
        <div className="flex gap-2"><Btn small kind="primary" onClick={save} loading={busy === 'save'} disabled={!!preview?.problems?.length}>Save</Btn>
          <Btn small onClick={draft} loading={busy === 'draft'}>{data?.map ? 'Redraft' : 'Draft again'}</Btn><Btn small kind="ghost" onClick={() => { setEditing(null); setPreview(null); setDraftNote(''); }}>Cancel</Btn></div>
      </div>}
      {!map && editing === null && <p className="text-sm text-zinc-500">No architecture yet.{onPhone ? ' Make one on the laptop.' : ' SmartWard can draft one from the project’s goal, brief and synced README, check it against a reference architecture, and hand it to you to edit.'}</p>}
      {map?.pattern_title && <div className="text-xs text-zinc-500">Checked against: {map.pattern_title}</div>}
      <div ref={box} className="max-h-[80vh] overflow-auto rounded-lg border border-zinc-800/60 p-2 [&_svg]:mx-auto" aria-label="Architecture diagram" />
      {map?.parts?.length > 0 && <div className="flex flex-wrap gap-2 text-[11px] text-zinc-500">{Object.entries(TONE).map(([k, [l, tone]]) => <Badge key={k} tone={tone}>{l}</Badge>)}<span>· numbers count items placed on each part · dashed border: suggested · dashed arrow: control</span>
        <button className="ml-auto text-zinc-400 hover:text-zinc-100" onClick={() => setFit(!fit)}>{fit ? 'Full size' : 'Fit to width'}</button></div>}
      {editing === null && map && <Checks checks={map.checks} />}
      {part && over && <div className="rounded-lg border border-zinc-800 p-3 text-sm">
        <div className="mb-1 flex flex-wrap items-center gap-2"><span className="font-medium">{part.label}</span><Badge>{part.type}</Badge>{part.zone && <Badge>{part.zone}</Badge>}{part.suggested && <Badge tone="indigo">suggested</Badge>}
          <Badge tone={TONE[over.tone][1]}>{TONE[over.tone][0]}</Badge><button className="ml-auto text-xs text-zinc-500 hover:text-zinc-200" onClick={() => setPicked(null)}>✕</button></div>
        {part.note && <p className="mb-1 text-xs text-zinc-400">Why: {part.note}</p>}
        <div className="mb-2 text-xs text-zinc-500">Words: {Object.entries(over.terms || {}).map(([t, n]: any) => `${t} (${n})`).join(', ') || '(none: its name is used)'}</div>
        {links.length > 0 && <ul className="mb-2 space-y-0.5 text-xs text-zinc-400">{links.map((e: any, i: number) => <li key={i}>{e.a === part.id ? `→ ${label(e.b)}` : `← ${label(e.a)}`}{e.verb ? `: ${e.verb}` : ''}{e.protocol ? ` (${e.protocol})` : ''}{e.kind === 'control' ? ' · control' : ''}</li>)}</ul>}
        {over.hypotheses.length > 0 && <ul className="mb-2 space-y-1">{over.hypotheses.map((h: any) => <li key={h.id} className="text-xs"><Badge tone={TONE[h.direction]?.[1] || 'zinc'}>{h.direction}</Badge> {h.headline} <span className="text-zinc-500">({h.status === 'new' ? 'to review' : 'accepted'})</span></li>)}</ul>}
        {over.developments.length > 0 ? <ul className="space-y-1">{over.developments.map((d: any) => <li key={d.id} className="text-xs"><span className="text-zinc-400">{d.evidence}</span> · {d.claim} <button className="text-indigo-300 hover:underline" onClick={() => openArticle(d.article_id)}>{d.source}</button>{d.source !== 'Test bench' && <TestThis devId={d.id} />}</li>)}
          {over.development_count > over.developments.length && <li className="text-xs text-zinc-500">and {over.development_count - over.developments.length} more</li>}</ul>
          : <p className="text-xs text-zinc-500">No recent developments use this part’s words.</p>}
      </div>}
    </Card>
  );
}
