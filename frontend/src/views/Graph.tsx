import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { errText, get, post } from '../api';
import { useLoad, useNav } from '../hooks';
import { isLight } from '../theme';
import { Badge, Btn, Card, Empty, Err, Field, inputCls, Modal, Seg, Title, cx } from '../ui';

/** A theme's dot grows with the square root of its strength, so one dominant theme doesn't swallow the rest. */
const radius = (n: any) => 3 + 2.2 * Math.sqrt(n.strength);
const COLORS: Record<string, string> = { model: '#a78bfa', tool: '#34d399', library: '#22d3ee', company: '#fbbf24', person: '#f472b6', concept: '#818cf8', technique: '#fb923c', benchmark: '#f87171', paper: '#60a5fa', project: '#a3e635', other: '#a1a1aa' };

export default function GraphView() {
  const { themeId, go, openArticle } = useNav();
  const [scope, setScope] = useState('all'); const [scopeId, setScopeId] = useState<number | undefined>(); const [dormant, setDormant] = useState(false);
  const [mode, setMode] = useState(typeof window !== 'undefined' && window.innerWidth < 900 ? 'list' : 'graph');
  const { data, error, reload } = useLoad<any>('/graph', { scope, scope_id: scopeId, dormant });
  const { data: projs } = useLoad<any[]>('/projects'); const { data: srcs } = useLoad<any[]>('/sources');
  const sel = themeId;
  const [hidden, setHidden] = useState<string[]>([]); const [q, setQ] = useState(''); const [hover, setHover] = useState<number | null>(null); const [pinned, setPinned] = useState(0);
  const box = useRef<HTMLDivElement>(null); const fg = useRef<any>(null); const [sz, setSz] = useState({ w: 400, h: 400 });
  useEffect(() => { fg.current?.d3Force?.('charge')?.strength(-260).distanceMax(260); fg.current?.d3Force?.('link')?.distance(80); }, [data]);
  useEffect(() => { const el = box.current; if (!el) return; const ro = new ResizeObserver(() => setSz({ w: el.clientWidth, h: el.clientHeight })); ro.observe(el); return () => ro.disconnect(); }, [mode]);
  // Keep each node's object (and so its position) across refreshes: the graph updates in place instead of re-laying out.
  const nodeCache = useRef(new Map<number, any>()); const fitted = useRef('');
  const scopeKey = `${scope}:${scopeId}:${dormant}`;
  const gdata = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    const seen = new Set<number>();
    const nodes = data.themes.filter((t: any) => !hidden.includes(t.type)).map((t: any) => { seen.add(t.id); const old = nodeCache.current.get(t.id); const n = old ? Object.assign(old, t, { val: 2 + t.strength * 3 }) : { ...t, val: 2 + t.strength * 3 }; nodeCache.current.set(t.id, n); return n; });
    for (const k of [...nodeCache.current.keys()]) if (!data.themes.some((t: any) => t.id === k)) nodeCache.current.delete(k);
    return { nodes, links: data.edges.filter((e: any) => seen.has(e.a) && seen.has(e.b)).map((e: any) => ({ source: e.a, target: e.b, w: e.weight })) };
  }, [data, hidden]);
  const allThemes: any[] = data?.themes || []; const types = [...new Set(allThemes.map(t => t.type))].sort();
  const themes: any[] = allThemes.filter(t => !hidden.includes(t.type) && (!q.trim() || t.name.toLowerCase().includes(q.trim().toLowerCase())));
  // Hovering a theme (or the selected one) lights it and the themes it connects to; everything else steps back.
  const focus = hover ?? sel ?? null;
  const near = useMemo(() => {
    const m = new Set<number>(); if (focus == null || !data) return m;
    for (const e of data.edges) { if (e.a === focus) m.add(e.b); else if (e.b === focus) m.add(e.a); }
    return m;
  }, [data, focus]);
  const idOf = (x: any) => (typeof x === 'object' ? x.id : x);
  const centre = (id: number) => { const n = nodeCache.current.get(id); if (n?.x != null && fg.current) { fg.current.centerAt(n.x, n.y, 500); if (fg.current.zoom() < 2) fg.current.zoom(2.5, 500); } };
  useEffect(() => { if (sel != null && mode === 'graph') centre(sel); }, [sel]);
  const zoomBy = (f: number) => fg.current?.zoom(fg.current.zoom() * f, 250);
  const unpin = () => { for (const n of nodeCache.current.values()) { n.fx = undefined; n.fy = undefined; } setPinned(0); fg.current?.d3ReheatSimulation?.(); };
  const matches = q.trim() ? themes.slice(0, 6) : [];

  return (
    <div className="flex h-full flex-col md:flex-row">
      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="space-y-2 border-b border-zinc-800 p-3">
          <Title right={<Seg value={mode} onChange={setMode} options={[['graph', 'Graph'], ['list', 'List']]} />}>Graph</Title>
          <div className="flex flex-wrap items-center gap-2">
            <select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs" aria-label="Scope" value={scope === 'all' || scope === 'recent' ? scope : scope + ':' + scopeId}
              onChange={e => { const [s, id] = e.target.value.split(':'); setScope(s); setScopeId(id ? Number(id) : undefined); }}>
              <option value="all">All themes</option><option value="recent">Last two weeks</option>
              {(projs || []).map(p => <option key={'p' + p.id} value={`project:${p.id}`}>Project: {p.name}</option>)}
              {(srcs || []).map(s => <option key={'s' + s.id} value={`source:${s.id}`}>Source: {s.name}</option>)}</select>
            <label className="flex items-center gap-1 text-xs text-zinc-400"><input type="checkbox" checked={dormant} onChange={e => setDormant(e.target.checked)} />Show dormant</label>
            <input className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs sm:max-w-56" aria-label="Find a theme" placeholder="Find a theme…" value={q} onChange={e => setQ(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && matches[0]) go('graph', { themeId: matches[0].id }); if (e.key === 'Escape') setQ(''); }} />
            {pinned > 0 && <Btn small onClick={unpin} title="Dragging a theme pins it where you drop it">Unpin {pinned}</Btn>}
            <span className="text-xs text-zinc-600">Strongest themes, with older mentions fading. Tap a type to hide it; drag a theme to pin it.</span></div>
          {matches.length > 0 && mode === 'graph' && <ul className="flex flex-wrap gap-1" aria-label="Matches">{matches.map(t => <li key={t.id}><button className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs hover:bg-zinc-800" onClick={() => { go('graph', { themeId: t.id }); centre(t.id); }}>{t.name}</button></li>)}</ul>}
          <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-zinc-400" aria-label="Legend">{types.map(t => <li key={t}><button aria-pressed={!hidden.includes(t)} onClick={() => setHidden(h => h.includes(t) ? h.filter(x => x !== t) : [...h, t])} className={cx('flex items-center gap-1 rounded-full px-1.5 py-0.5 hover:bg-zinc-800', hidden.includes(t) && 'line-through opacity-40')}><span className="h-2 w-2 rounded-full" style={{ background: COLORS[t] || COLORS.other }} aria-hidden />{t}</button></li>)}</ul></div>
        <Err>{error}</Err>
        <div ref={box} className="relative min-h-0 flex-1 overflow-hidden">
          {themes.length === 0 && allThemes.length > 0 ? (
            <Empty icon="⁂" title="Nothing matches"><div className="mt-3"><Btn onClick={() => { setHidden([]); setQ(''); }}>Clear search and type filters</Btn></div></Empty>
          ) : themes.length === 0 ? (
            <Empty icon="⁂" title="No themes in this scope">{scope !== 'all' || !dormant ? <>Themes appear as articles are read and indexed. <div className="mt-3"><Btn onClick={() => { setScope('all'); setScopeId(undefined); setDormant(true); }}>Show every theme</Btn></div></> : 'Themes appear as articles are indexed.'}</Empty>
          ) : mode === 'graph' ? (
            <ForceGraph2D ref={fg} onEngineStop={() => { if (fitted.current !== scopeKey) { fitted.current = scopeKey; fg.current?.zoomToFit(400, 70); } }} d3VelocityDecay={0.3} width={sz.w} height={sz.h} graphData={gdata} backgroundColor="rgba(0,0,0,0)" cooldownTicks={120}
              nodeLabel={(n: any) => `${n.name} (${n.type})`} onNodeClick={(n: any) => go('graph', { themeId: n.id })}
              nodePointerAreaPaint={(n: any, color: string, ctx: CanvasRenderingContext2D) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(n.x, n.y, radius(n) + 2, 0, 2 * Math.PI); ctx.fill(); }}
              onNodeHover={(n: any) => setHover(n ? n.id : null)} onNodeDragEnd={(n: any) => { n.fx = n.x; n.fy = n.y; setPinned([...nodeCache.current.values()].filter(x => x.fx != null).length); }}
              onBackgroundClick={() => { if (sel != null) go('graph', { themeId: null }); }}
              linkColor={(l: any) => focus == null ? 'rgba(113,113,122,.5)' : idOf(l.source) === focus || idOf(l.target) === focus ? 'rgba(129,140,248,.95)' : 'rgba(113,113,122,.12)'}
              linkWidth={(l: any) => Math.min(4, l.w) * (focus != null && (idOf(l.source) === focus || idOf(l.target) === focus) ? 1.5 : 1)}
              nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, k: number) => {
                const r = radius(n); ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI); ctx.fillStyle = COLORS[n.type] || COLORS.other; const lit = focus == null || n.id === focus || near.has(n.id); ctx.globalAlpha = (n.dormant ? 0.35 : 1) * (lit ? 1 : 0.15); ctx.fill();
                if (n.id === sel) { ctx.lineWidth = 1.5 / k; ctx.strokeStyle = isLight() ? '#000' : '#fff'; ctx.stroke(); }
                ctx.globalAlpha = lit ? 1 : 0.2; if (!(focus != null && lit) && k < 0.8 && n.strength < 2 && n.id !== sel) return; ctx.font = `${Math.max(3, 11 / k)}px sans-serif`; ctx.fillStyle = isLight() ? '#27272a' : '#e4e4e7'; ctx.textAlign = 'center'; ctx.fillText(n.name, n.x, n.y + r + 8 / k); ctx.globalAlpha = 1;
              }} />
          ) : (
            <ul className="h-full overflow-y-auto" aria-label="Themes">{themes.map(t => (
              <li key={t.id}><button onClick={() => go('graph', { themeId: t.id })} className={cx('flex w-full items-center gap-3 border-b border-zinc-800/70 px-4 py-2.5 text-left hover:bg-zinc-900', sel === t.id && 'bg-zinc-900')}>
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[t.type] || COLORS.other }} /><span className="flex-1 text-sm">{t.name}</span><Badge>{t.type}</Badge>
                <span className="w-24 text-right text-xs text-zinc-500">strength {t.strength.toFixed(1)} · {t.articles}</span></button></li>))}</ul>)}
          {mode === 'graph' && themes.length > 0 && <div className="absolute bottom-3 right-3 flex flex-col gap-1">
            <Btn small onClick={() => zoomBy(1.5)} label="Zoom in">+</Btn><Btn small onClick={() => zoomBy(1 / 1.5)} label="Zoom out">−</Btn><Btn small onClick={() => fg.current?.zoomToFit(400, 70)} label="Fit everything">⤢</Btn></div>}
        </div>
      </section>
      {sel != null && <ThemeDetail id={sel} onClose={() => go('graph', { themeId: null })} onChanged={reload} openArticle={openArticle} />}
    </div>
  );
}

function ThemeDetail({ id, onClose, onChanged, openArticle }: { id: number; onClose: () => void; onChanged: () => void; openArticle: (id: number) => void }) {
  const { data: t, error, reload } = useLoad<any>(`/themes/${id}`);
  const { go } = useNav(); const [dlg, setDlg] = useState<'' | 'rename' | 'merge' | 'split'>('');
  if (error) return <aside className="w-full border-l border-zinc-800 p-4 md:w-96"><Err>{error}</Err><Btn onClick={onClose}>Close</Btn></aside>;
  if (!t) return null;
  return (
    <aside className="min-h-0 w-full overflow-y-auto border-t border-zinc-800 p-4 md:w-96 md:border-l md:border-t-0" aria-label="Theme detail">
      <div className="mb-2 flex items-start justify-between"><div><h2 className="text-lg font-semibold">{t.name}</h2><div className="text-xs text-zinc-500">{t.type} · strength {t.strength.toFixed(2)}</div></div><button onClick={onClose} aria-label="Close" className="text-zinc-500">✕</button></div>
      <div className="mb-3 flex flex-wrap gap-1.5"><Btn small onClick={() => setDlg('rename')}>Rename</Btn><Btn small onClick={() => setDlg('merge')}>Merge into…</Btn><Btn small onClick={() => setDlg('split')}>Split</Btn></div>
      {t.aliases.length > 0 && <div className="mb-3 text-xs text-zinc-500">Also known as: {t.aliases.join(', ')}</div>}
      {t.projects.length > 0 && <div className="mb-3 flex flex-wrap gap-1 text-xs"><span className="text-zinc-500">Pinned by</span>{t.projects.map((p: any) => <button key={p.id} onClick={() => go('projects', { projectId: p.id })}><Badge tone="green">{p.name}</Badge></button>)}</div>}
      <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">Connections</h3>
      {t.connections.length === 0 ? <div className="mb-3 text-sm text-zinc-500">None yet.</div> : <ul className="mb-3 space-y-1">{t.connections.map((c: any, i: number) => <li key={i} className="text-sm"><button className="text-indigo-300 hover:underline" onClick={() => go('graph', { themeId: c.id })}>{c.name}</button> <span className="text-xs text-zinc-500">{c.relation} ×{c.n}</span></li>)}</ul>}
      <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">Where it came up</h3>
      <ul className="space-y-1">{t.articles.map((a: any) => <li key={a.id}><button className="text-left text-sm text-zinc-300 hover:text-zinc-50 hover:underline" onClick={() => openArticle(a.id)}>{a.title}</button></li>)}</ul>
      {dlg && <ThemeDialog kind={dlg} t={t} onClose={() => setDlg('')} onDone={(newId?: number) => { setDlg(''); onChanged(); if (newId && newId !== id) go('graph', { themeId: newId }); else reload(); }} />}
    </aside>
  );
}

function ThemeDialog({ kind, t, onClose, onDone }: { kind: string; t: any; onClose: () => void; onDone: (id?: number) => void }) {
  const { data: all } = useLoad<any[]>('/themes'); const [name, setName] = useState(kind === 'rename' ? t.name : ''); const [into, setInto] = useState('');
  const [pick, setPick] = useState<number[]>([]); const [err, setErr] = useState('');
  const go = async () => {
    try {
      if (kind === 'rename') { const r = await post(`/themes/${t.id}/rename`, { name }); onDone(r.id); }
      else if (kind === 'merge') { const r = await post(`/themes/${t.id}/merge`, { into: Number(into) }); onDone(r.id); }
      else { const r = await post(`/themes/${t.id}/split`, { name, article_ids: pick }); onDone(t.id); }
    } catch (e) { setErr(errText(e)); }
  };
  return (
    <Modal title={kind === 'rename' ? 'Rename theme' : kind === 'merge' ? `Merge “${t.name}” into another` : `Split “${t.name}”`} onClose={onClose}>
      <div className="space-y-3">
        {kind !== 'merge' && <Field label={kind === 'split' ? 'New theme name' : 'Name'}><input className={inputCls} value={name} onChange={e => setName(e.target.value)} autoFocus /></Field>}
        {kind === 'merge' && <Field label="Merge into" hint="Its name becomes an alias, so new articles resolve to the target. Your corrections always win."><select className={inputCls} value={into} onChange={e => setInto(e.target.value)}><option value="">Choose…</option>{(all || []).filter(x => x.id !== t.id).map(x => <option key={x.id} value={x.id}>{x.name} ({x.type})</option>)}</select></Field>}
        {kind === 'split' && <Field label="Move these articles to the new theme">{t.articles.map((a: any) => <label key={a.id} className="flex items-start gap-2 py-0.5 text-sm"><input type="checkbox" className="mt-1" checked={pick.includes(a.id)} onChange={e => setPick(e.target.checked ? [...pick, a.id] : pick.filter(x => x !== a.id))} />{a.title}</label>)}</Field>}
        <Err>{err}</Err>
        <div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" onClick={go} disabled={kind === 'merge' ? !into : !name.trim() || (kind === 'split' && !pick.length)}>{kind === 'rename' ? 'Rename' : kind === 'merge' ? 'Merge' : 'Split'}</Btn></div>
      </div>
    </Modal>
  );
}
