import { useEffect, useRef, useState } from 'react';
import { errText, post, put } from '../api';
import { onPhone } from '../device';
import { toast } from '../feedback';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Err, inputCls } from '../ui';
import { TestThis } from './Bench';

const TONE: Record<string, [string, 'red' | 'green' | 'indigo' | 'zinc']> = { threatens: ['Could undercut', 'red'], accelerates: ['Could speed up', 'green'], enables: ['Could open up', 'indigo'], news: ['Recent news', 'zinc'], quiet: ['Quiet', 'zinc'] };
const EXAMPLE = 'Serving layer: vllm, continuous batching\nKV cache: kv cache, prefix caching\nModel: llama, qwen, quantization\n\nServing layer -> KV cache\nKV cache -> Model\n';
let seq = 0;

/** Draws Mermaid source into an element. Mermaid loads only when a map is shown; strict mode means diagram text can never run scripts. */
async function draw(el: HTMLElement, src: string, onPick: (id: string) => void) {
  const { default: mermaid } = await import('mermaid');
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: document.documentElement.dataset.theme === 'light' ? 'default' : 'dark', flowchart: { htmlLabels: false } });
  const { svg } = await mermaid.render(`project-map-${++seq}`, src);
  el.innerHTML = svg;
  el.querySelectorAll<SVGGElement>('g.node').forEach(g => {
    const id = /flowchart-(c\d+)-/.exec(g.id)?.[1]; if (!id) return;
    g.style.cursor = 'pointer'; g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button');
    g.addEventListener('click', () => onPick(id)); g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick(id); } });
  });
}

/** The project's stack as a diagram, with recent developments and this project's hypotheses placed on the part they touch. */
export default function ProjectMap({ pid }: { pid: number }) {
  const { data, reload } = useLoad<any>(`/projects/${pid}/map`);
  const { openArticle } = useNav();
  const [editing, setEditing] = useState<string | null>(null); const [preview, setPreview] = useState<any>(null);
  const [picked, setPicked] = useState<string | null>(null); const [busy, setBusy] = useState(''); const [err, setErr] = useState('');
  const box = useRef<HTMLDivElement>(null);
  const map = editing !== null ? preview : data?.map;

  useEffect(() => {                                 // while editing, redraw from the lines as you type (nothing is saved)
    if (editing === null) return;
    const t = setTimeout(() => post(`/projects/${pid}/map/preview`, { text: editing }).then(setPreview).catch(() => {}), 350);
    return () => clearTimeout(t);
  }, [editing, pid]);
  useEffect(() => {
    if (!box.current || !map?.components?.length) { if (box.current) box.current.innerHTML = ''; return; }
    draw(box.current, map.mermaid, setPicked).catch(e => setErr('Couldn’t draw the map: ' + (e?.message || e)));
  }, [map?.mermaid]);

  const draft = async () => {
    setBusy('draft'); setErr('');
    try { const d = await post(`/projects/${pid}/map/draft`); setEditing(d.text); toast.ok('Here’s a first draft. Edit it, then Save.'); }
    catch (e) { setErr(errText(e)); }
    setBusy('');
  };
  const save = async () => { setBusy('save'); setErr(''); try { await put(`/projects/${pid}/map`, { text: editing }); setEditing(null); setPreview(null); reload(); } catch (e) { setErr(errText(e)); } setBusy(''); };
  const download = () => {
    const svg = box.current?.querySelector('svg'); if (!svg) return;
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([svg.outerHTML], { type: 'image/svg+xml' })); a.download = 'project-map.svg'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  };
  const comp = map?.components?.find((c: any) => c.id === picked); const over = picked ? map?.overlay?.[picked] : null;

  return (
    <Card className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-medium">Stack map</h2>
        <div className="text-xs text-zinc-500">The parts of this project, with recent developments and implications placed on the part they mention. Click a part.</div></div>
        {!onPhone && editing === null && <div className="flex flex-wrap gap-2">
          {data?.map && <><Btn small onClick={download}>⤓ SVG</Btn><Btn small onClick={() => { setEditing(data.map.text); setPicked(null); }}>Edit</Btn></>}
          {!data?.map && <><Btn small kind="primary" onClick={draft} loading={busy === 'draft'}>Draft it for me</Btn><Btn small onClick={() => setEditing(EXAMPLE)}>Write it myself</Btn></>}</div>}
      </div>
      <Err>{err}</Err>
      {editing !== null && <div className="space-y-2">
        <textarea className={inputCls + ' h-40 font-mono text-xs'} value={editing} onChange={e => setEditing(e.target.value)} aria-label="Stack map lines" spellCheck={false} />
        <div className="text-xs text-zinc-500">One part per line as <code>Name: words, that, mean, it</code>; connections as <code>Name -&gt; Other name</code>. An item lands on a part when it uses one of its words.</div>
        {preview?.problems?.length > 0 && <ul className="text-xs text-amber-300">{preview.problems.map((p: string) => <li key={p}>{p}</li>)}</ul>}
        <div className="flex gap-2"><Btn small kind="primary" onClick={save} loading={busy === 'save'} disabled={!!preview?.problems?.length}>Save</Btn>
          {!data?.map && <Btn small onClick={draft} loading={busy === 'draft'}>Draft again</Btn>}<Btn small kind="ghost" onClick={() => { setEditing(null); setPreview(null); }}>Cancel</Btn></div>
      </div>}
      {!map && editing === null && <p className="text-sm text-zinc-500">No map yet.{onPhone ? ' Make one on the laptop.' : ' SmartWard can draft one from the project’s goal, brief and synced README for you to edit.'}</p>}
      <div ref={box} className="overflow-x-auto [&_svg]:mx-auto [&_svg]:max-w-full" aria-label="Stack map diagram" />
      {map?.components?.length > 0 && <div className="flex flex-wrap gap-2 text-[11px] text-zinc-500">{Object.entries(TONE).map(([k, [label, tone]]) => <Badge key={k} tone={tone}>{label}</Badge>)}<span>· numbers count items placed on each part</span></div>}
      {comp && over && <div className="rounded-lg border border-zinc-800 p-3 text-sm">
        <div className="mb-1 flex flex-wrap items-center gap-2"><span className="font-medium">{comp.label}</span><Badge tone={TONE[over.tone][1]}>{TONE[over.tone][0]}</Badge>
          <span className="text-xs text-zinc-500">{comp.terms.join(', ')}</span><button className="ml-auto text-xs text-zinc-500 hover:text-zinc-200" onClick={() => setPicked(null)}>✕</button></div>
        {over.hypotheses.length > 0 && <ul className="mb-2 space-y-1">{over.hypotheses.map((h: any) => <li key={h.id} className="text-xs"><Badge tone={TONE[h.direction]?.[1] || 'zinc'}>{h.direction}</Badge> {h.headline} <span className="text-zinc-500">({h.status === 'new' ? 'to review' : 'accepted'})</span></li>)}</ul>}
        {over.developments.length > 0 ? <ul className="space-y-1">{over.developments.map((d: any) => <li key={d.id} className="text-xs"><span className="text-zinc-400">{d.evidence}</span> · {d.claim} <button className="text-indigo-300 hover:underline" onClick={() => openArticle(d.article_id)}>{d.source}</button>{d.source !== 'Test bench' && <TestThis devId={d.id} />}</li>)}
          {over.development_count > over.developments.length && <li className="text-xs text-zinc-500">and {over.development_count - over.developments.length} more</li>}</ul>
          : <p className="text-xs text-zinc-500">No recent developments mention this part’s words.</p>}
      </div>}
    </Card>
  );
}
