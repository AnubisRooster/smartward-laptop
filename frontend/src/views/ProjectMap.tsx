import { useEffect, useRef, useState } from 'react';
import { errText, get, post, put } from '../api';
import { onPhone } from '../device';
import { ask, toast } from '../feedback';
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

const PARTS: [string, string, number][] = [['correctness', 'Correctness', 25], ['practice', 'Best practices', 35], ['completeness', 'Reference pattern', 15], ['fidelity', 'Matches the brief', 15], ['evidence', 'Evidence in your reading', 10]];
const AREA: Record<string, string> = { correctness: 'Correctness', clarity: 'Clarity', security: 'Security', data: 'Data protection', governance: 'Governance', reliability: 'Reliability', observability: 'Observability & cost' };
const tone = (n: number) => n >= 85 ? 'text-emerald-400' : n >= 65 ? 'text-amber-300' : 'text-red-400';

/** The weighted score: correctness, best practices (OWASP, Well-Architected, NIST AI RMF, zero trust, C4), the reference pattern, the brief and the evidence,
 * with every unmet rule, its source and its fix, and a way to waive one with a reason. */
function Scorecard({ sc, reviewed, notes, onReview, reviewing, onWaive, open }: { sc: any; reviewed: boolean; notes: any[]; onReview?: () => void; reviewing?: boolean; onWaive?: (id: string) => void; open?: boolean }) {
  if (!sc) return null;
  const fails = sc.rules.filter((r: any) => !r.ok), met = sc.rules.filter((r: any) => r.ok && !r.waived);
  const byArea: Record<string, any[]> = {}; fails.forEach((r: any) => (byArea[r.area] ||= []).push(r));
  const rev = sc.review;
  return (
    <details open={open} className="rounded-lg border border-zinc-800 p-2 text-xs">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2"><span className={'text-lg font-semibold ' + tone(sc.total)}>{sc.total}</span><span className="text-zinc-400">/ 100 architecture score · {fails.length} rule{fails.length === 1 ? '' : 's'} to fix{sc.missing.length ? `, ${sc.missing.length} expected part${sc.missing.length === 1 ? '' : 's'} missing` : ''}</span>
        <span className="ml-auto text-zinc-500" title="Set a capable review model in Settings → Model for better reviews">{reviewed ? `reviewed by ${(rev?.model || '').replace(/^openrouter\//, '')}` : 'not reviewed by the second model'}</span>
        {onReview && <Btn small onClick={onReview} loading={reviewing} title="A second model checks arrow directions, protocols and the brief's requirements">{reviewed ? 'Review again' : 'Review now'}</Btn>}</summary>
      <div className="mt-2 grid gap-1 sm:grid-cols-5">{PARTS.map(([k, label, w]) => sc.parts[k] !== undefined && (
        <div key={k} title={`${w}% of the score` + (k === 'evidence' && !sc.evidence_reviewed ? ' · counted at 60% until a reviewer checks the words' : '')}><div className="flex justify-between text-zinc-400"><span>{label}{k === 'evidence' && !sc.evidence_reviewed ? ' (unchecked)' : ''}</span><span className={tone(sc.parts[k])}>{sc.parts[k]}</span></div>
          <div className="h-1 rounded bg-zinc-800"><div className={'h-1 rounded ' + (sc.parts[k] >= 85 ? 'bg-emerald-500' : sc.parts[k] >= 65 ? 'bg-amber-400' : 'bg-red-500')} style={{ width: sc.parts[k] + '%' }} /></div></div>))}</div>
      {Object.entries(byArea).map(([area, rs]) => (
        <div key={area} className="mt-2"><div className="font-medium text-zinc-300">{AREA[area] || area}</div>
          <ul className="space-y-1">{rs.map((r: any) => (
            <li key={r.id} className="rounded border border-zinc-800/70 p-1.5"><div className="flex flex-wrap items-center gap-1"><span className="text-amber-300">{'●'.repeat(r.weight)}</span><span className="font-medium">{r.id} {r.title}</span>{r.detail && <span className="text-zinc-500">— {r.detail}</span>}
              {onWaive && !r.id.startsWith('J') && <button className="ml-auto text-zinc-500 hover:text-zinc-200" onClick={() => onWaive(r.id)}>waive…</button>}</div>
              <div className="text-zinc-400">{r.why} <span className="text-zinc-300">Fix: {r.fix}</span></div><div className="text-zinc-500">Source: {r.ref}</div></li>))}</ul></div>))}
      {sc.missing.length > 0 && <div className="mt-2"><div className="font-medium text-zinc-300">Expected for this kind of system</div><ul>{sc.missing.map((x: any) => <li key={x.name} className="text-amber-300">● {x.name} <span className="text-zinc-400">— {x.why}</span></li>)}</ul></div>}
      {(sc.brief.some((b: any) => !b.present) || sc.constraints.some((c: any) => !c.met)) && <div className="mt-2"><div className="font-medium text-zinc-300">From your brief</div><ul>
        {sc.brief.filter((b: any) => !b.present).map((b: any) => <li key={b.component} className="text-amber-300">● “{b.component}” isn’t on the map</li>)}
        {sc.constraints.filter((c: any) => !c.met).map((c: any) => <li key={c.text} className="text-amber-300">● {c.text} <span className="text-zinc-400">— {c.why}</span></li>)}</ul></div>}
      {sc.waived.length > 0 && <div className="mt-2 text-zinc-400">Waived: {sc.waived.map((w: any) => `${w.id} ${w.title} (${w.reason})`).join('; ')}</div>}
      {met.length > 0 && <details className="mt-2"><summary className="cursor-pointer text-zinc-500">Met ({met.length})</summary><div className="text-zinc-500">{met.map((r: any) => `${r.id} ${r.title}`).join(' · ')}</div></details>}
      {notes?.length > 0 && <details className="mt-1"><summary className="cursor-pointer text-zinc-500">Other notes ({notes.length})</summary><ul className="text-zinc-500">{notes.map((c: any, i: number) => <li key={i}>· {c.text}</li>)}</ul></details>}
    </details>
  );
}

/** Per part: how many recent developments its words match, and each word's own count, so words nobody uses stand out while you type. */
function Matches({ map }: { map: any }) {
  return (
    <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-left text-zinc-500"><th className="py-1 pr-2 font-normal">Part</th><th className="pr-2 font-normal">Matches</th><th className="font-normal">Words (matches each)</th></tr></thead>
      <tbody>{map.parts.map((p: any) => { const o = map.overlay[p.id] || {}; return (
        <tr key={p.id} className="border-t border-zinc-800 align-top"><td className="py-1 pr-2">{p.suggested && <span title="Suggested by SmartWard">~</span>}{p.label} <span className="text-zinc-500">{p.type}{p.zone ? ` · ${p.zone}` : ''}</span></td>
          <td className={'pr-2 ' + (o.development_count ? 'text-zinc-200' : 'text-amber-300')}>{o.development_count || 0}</td>
          <td>{Object.entries(o.terms || {}).map(([t, n]: any) => o.ignored?.[t]
            ? <span key={t} className="mr-2 text-zinc-500 line-through" title={`Not counted: ${o.ignored[t]}`}>{t} {n}</span>
            : <span key={t} className={'mr-2 ' + (n ? 'text-zinc-300' : 'text-amber-300/80')}>{t} {n}</span>)}</td></tr>); })}</tbody></table>
      <p className="mt-1 text-[11px] text-zinc-500">Struck-through words don’t count as evidence: too broad, used on more than one part, or not about the part (per the reviewer). Hover for why.</p></div>
  );
}

/** The project's architecture as a diagram, with recent developments and implications placed on the part they mention. */
export default function ProjectMap({ pid }: { pid: number }) {
  const { data, reload } = useLoad<any>(`/projects/${pid}/map`);
  const { openArticle } = useNav();
  const [editing, setEditing] = useState<string | null>(null); const [preview, setPreview] = useState<any>(null); const [draftNote, setDraftNote] = useState('');
  const [picked, setPicked] = useState<string | null>(null); const [busy, setBusy] = useState(''); const [err, setErr] = useState(''); const [fit, setFit] = useState(false); const [progress, setProgress] = useState('');
  const review = async () => {
    setBusy('review'); setErr('');
    try { const r = await post(`/projects/${pid}/map/review`, { text: editing ?? data?.map?.text }); if (editing !== null) setPreview(r); else reload(); }
    catch (e) { setErr(errText(e)); }
    setBusy('');
  };
  const waive = async (id: string) => {
    const why = await ask.prompt({ title: `Waive ${id}?`, body: 'Say why this rule doesn’t apply here. It is kept in the map as “@waive”, so the decision stays visible.', label: 'Reason', confirmLabel: 'Waive' });
    if (!why?.trim()) return;
    const line = `@waive ${id}: ${why.trim()}\n`;
    if (editing !== null) { setEditing(line + editing); return; }
    try { await put(`/projects/${pid}/map`, { text: line + data.map.text }); reload(); } catch (e) { toast.error(errText(e)); }
  };
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

  const follow = async () => {                       // poll a running draft until it ends, then take the result (once)
    setBusy('draft'); setErr('');
    try {
      let st: any = null;
      for (let i = 0; i < 600; i++) {                     // up to 30 minutes; free models can be slow
        st = await get(`/projects/${pid}/map/draft/status`);
        setProgress(`${st.step || ''} · ${Math.floor((st.elapsed || 0) / 60)}m ${(st.elapsed || 0) % 60}s`);
        if (!st.running) break;
        await new Promise(r => setTimeout(r, 3000));
      }
      st = await get(`/projects/${pid}/map/draft/status`, { take: true });
      if (st?.error) throw new Error(st.error);
      const d = st?.result; if (!d) throw new Error('The draft didn’t finish. Try again.');
      setEditing(d.text); setPicked(null);
      const steps = (d.history || []).map((h: any) => h.step === 'drafts' ? `${h.scores.length} drafts scored ${h.scores.join(', ')}` : h.step === 'review' ? `reviewed: ${h.score}`
        : h.step === 'repair' ? `repaired to ${h.score}` : h.step === 'repair rejected' ? `a repair was not used (${h.error})` : `${h.step} (${h.error})`).join(' → ');
      setDraftNote(`Drafted with ${d.model.replace(/^openrouter\//, '')}${d.reviewer ? `, reviewed by ${d.reviewer.replace(/^openrouter\//, '')}` : ''}. ${steps}. Dashed parts are suggestions: keep or delete them, then Save.`);
    } catch (e) { setErr(e instanceof Error && !('response' in e) ? e.message : errText(e)); }
    setBusy(''); setProgress('');
  };
  const draft = async () => {
    setDraftNote(''); setProgress('Starting');
    try { await post(`/projects/${pid}/map/draft`); } catch (e) { setErr(errText(e)); return; }
    follow();
  };
  useEffect(() => {                                 // a draft started earlier (this page was left) is picked up again
    if (onPhone) return;
    get(`/projects/${pid}/map/draft/status`).then(st => { if (st.running || st.result || st.error) follow(); }).catch(() => {});
  }, [pid]);
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
      {busy === 'draft' && <p className="text-xs text-zinc-400" role="status">Drafting three versions, scoring them against the best-practice rules, having a second model review the best one, and repairing it up to twice. Free models can take 10 minutes or more; you can leave this page and come back.<br /><span className="text-zinc-300">{progress}</span></p>}
      {editing !== null && <div className="space-y-2">
        {draftNote && <p className="text-xs text-indigo-300">{draftNote}</p>}
        <textarea className={inputCls + ' h-56 font-mono text-xs'} value={editing} onChange={e => setEditing(e.target.value)} aria-label="Architecture lines" spellCheck={false} />
        <details className="text-xs text-zinc-500"><summary className="cursor-pointer">How to write it</summary>
          <ul className="mt-1 space-y-0.5"><li><code>Name (type): words, articles, use</code> a part. Types: {TYPES.map(([t, s, d]) => <span key={t} className="mr-2" title={d}>{s} <code>{t}</code></span>)}</li>
            <li><code>[On-prem data center]</code> parts below it run there, until the next <code>[zone]</code>; <code>[]</code> ends it.</li>
            <li><code>A -&gt; B: what flows (protocol)</code> requests or data; <code>A =&gt; B: deploys</code> control.</li>
            <li><code>~Name …  # why</code> a suggested part, drawn dashed; <code>@pattern agent_platform</code> checks it against a reference (agent_platform, llm_serving, rag, hybrid_routing, none); <code>@waive S3: reason</code> sets a rule aside, on the record.</li>
            <li>Words match whole words in recent developments; plurals and hyphens are allowed. Amber numbers are words no article uses yet.</li></ul></details>
        {preview?.problems?.length > 0 && <ul className="text-xs text-red-300">{preview.problems.map((p: string) => <li key={p}>{p}</li>)}</ul>}
        {preview && <Scorecard sc={preview.score} reviewed={preview.reviewed} notes={preview.checks} onReview={onPhone ? undefined : review} reviewing={busy === 'review'} onWaive={waive} open />}
        {preview?.parts?.length > 0 && <Matches map={preview} />}
        <div className="flex gap-2"><Btn small kind="primary" onClick={save} loading={busy === 'save'} disabled={!!preview?.problems?.length}>Save</Btn>
          <Btn small onClick={draft} loading={busy === 'draft'}>{data?.map ? 'Redraft' : 'Draft again'}</Btn><Btn small kind="ghost" onClick={() => { setEditing(null); setPreview(null); setDraftNote(''); }}>Cancel</Btn></div>
      </div>}
      {!map && editing === null && <p className="text-sm text-zinc-500">No architecture yet.{onPhone ? ' Make one on the laptop.' : ' SmartWard can draft one from the project’s goal, brief and synced README, check it against a reference architecture, and hand it to you to edit.'}</p>}
      {map?.pattern_title && <div className="text-xs text-zinc-500">Checked against: {map.pattern_title}</div>}
      <div ref={box} className="max-h-[80vh] overflow-auto rounded-lg border border-zinc-800/60 p-2 [&_svg]:mx-auto" aria-label="Architecture diagram" />
      {map?.parts?.length > 0 && <div className="flex flex-wrap gap-2 text-[11px] text-zinc-500">{Object.entries(TONE).map(([k, [l, tone]]) => <Badge key={k} tone={tone}>{l}</Badge>)}<span>· numbers count items placed on each part · dashed border: suggested · dashed arrow: control</span>
        <button className="ml-auto text-zinc-400 hover:text-zinc-100" onClick={() => setFit(!fit)}>{fit ? 'Full size' : 'Fit to width'}</button></div>}
      {editing === null && map && <Scorecard sc={map.score} reviewed={map.reviewed} notes={map.checks} onReview={onPhone ? undefined : review} reviewing={busy === 'review'} onWaive={onPhone ? undefined : waive} />}
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
