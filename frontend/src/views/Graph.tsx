import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { errText, get, post } from '../api';
import { useLoad, useNav } from '../hooks';
import { isLight } from '../theme';
import { Badge, Btn, Card, Empty, Err, Field, inputCls, Modal, Seg, Title, cx } from '../ui';

const COLORS: Record<string, string> = { model: '#a78bfa', tool: '#34d399', library: '#22d3ee', company: '#fbbf24', person: '#f472b6', concept: '#818cf8', technique: '#fb923c', benchmark: '#f87171', paper: '#60a5fa', project: '#a3e635', other: '#a1a1aa' };

export default function GraphView() {
  const { themeId, go, openArticle } = useNav();
  const [scope, setScope] = useState('all'); const [scopeId, setScopeId] = useState<number | undefined>(); const [dormant, setDormant] = useState(false);
  const [mode, setMode] = useState(typeof window !== 'undefined' && window.innerWidth < 900 ? 'list' : 'graph');
  const { data, error, reload } = useLoad<any>('/graph', { scope, scope_id: scopeId, dormant });
  const { data: projs } = useLoad<any[]>('/projects'); const { data: srcs } = useLoad<any[]>('/sources');
  const sel = themeId;
  const box = useRef<HTMLDivElement>(null); const fg = useRef<any>(null); const [sz, setSz] = useState({ w: 400, h: 400 });
  useEffect(() => { fg.current?.d3Force?.('charge')?.strength(-160); fg.current?.d3Force?.('link')?.distance(70); }, [data]);
  useEffect(() => { const el = box.current; if (!el) return; const ro = new ResizeObserver(() => setSz({ w: el.clientWidth, h: el.clientHeight })); ro.observe(el); return () => ro.disconnect(); }, [mode]);
  // Keep each node's object (and so its position) across refreshes: the graph updates in place instead of re-laying out.
  const nodeCache = useRef(new Map<number, any>()); const fitted = useRef('');
  const scopeKey = `${scope}:${scopeId}:${dormant}`;
  const gdata = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    const seen = new Set<number>();
    const nodes = data.themes.map((t: any) => { seen.add(t.id); const old = nodeCache.current.get(t.id); const n = old ? Object.assign(old, t, { val: 2 + t.strength * 3 }) : { ...t, val: 2 + t.strength * 3 }; nodeCache.current.set(t.id, n); return n; });
    for (const k of [...nodeCache.current.keys()]) if (!seen.has(k)) nodeCache.current.delete(k);
    return { nodes, links: data.edges.map((e: any) => ({ source: e.a, target: e.b, w: e.weight })) };
  }, [data]);
  const themes: any[] = data?.themes || [];

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
            <span className="text-xs text-zinc-600">Strongest themes, with older mentions fading.</span></div>
          <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-zinc-400" aria-label="Legend">{[...new Set(themes.map(t => t.type))].sort().map(t => <li key={t} className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: COLORS[t] || COLORS.other }} aria-hidden />{t}</li>)}</ul></div>
        <Err>{error}</Err>
        <div ref={box} className="relative min-h-0 flex-1 overflow-hidden">
          {themes.length === 0 ? (
            <Empty icon="⁂" title="No themes in this scope">{scope !== 'all' || !dormant ? <>Themes appear as articles are read and indexed. <div className="mt-3"><Btn onClick={() => { setScope('all'); setScopeId(undefined); setDormant(true); }}>Show every theme</Btn></div></> : 'Themes appear as articles are indexed.'}</Empty>
          ) : mode === 'graph' ? (
            <ForceGraph2D ref={fg} onEngineStop={() => { if (fitted.current !== scopeKey) { fitted.current = scopeKey; fg.current?.zoomToFit(400, 70); } }} d3VelocityDecay={0.3} width={sz.w} height={sz.h} graphData={gdata} backgroundColor="rgba(0,0,0,0)" cooldownTicks={120}
              nodeLabel={(n: any) => `${n.name} (${n.type})`} onNodeClick={(n: any) => go('graph', { themeId: n.id })}
              linkColor={() => 'rgba(113,113,122,.5)'} linkWidth={(l: any) => Math.min(4, l.w)}
              nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, k: number) => {
                const r = 3 + n.strength * 2; ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI); ctx.fillStyle = COLORS[n.type] || COLORS.other; ctx.globalAlpha = n.dormant ? 0.35 : 1; ctx.fill();
                if (n.id === sel) { ctx.lineWidth = 1.5 / k; ctx.strokeStyle = isLight() ? '#000' : '#fff'; ctx.stroke(); }
                ctx.globalAlpha = 1; if (k < 0.8 && n.strength < 2 && n.id !== sel) return; ctx.font = `${Math.max(3, 11 / k)}px sans-serif`; ctx.fillStyle = isLight() ? '#27272a' : '#e4e4e7'; ctx.textAlign = 'center'; ctx.fillText(n.name, n.x, n.y + r + 8 / k);
              }} />
          ) : (
            <ul className="h-full overflow-y-auto" aria-label="Themes">{themes.map(t => (
              <li key={t.id}><button onClick={() => go('graph', { themeId: t.id })} className={cx('flex w-full items-center gap-3 border-b border-zinc-800/70 px-4 py-2.5 text-left hover:bg-zinc-900', sel === t.id && 'bg-zinc-900')}>
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[t.type] || COLORS.other }} /><span className="flex-1 text-sm">{t.name}</span><Badge>{t.type}</Badge>
                <span className="w-24 text-right text-xs text-zinc-500">strength {t.strength.toFixed(1)} · {t.articles}</span></button></li>))}</ul>)}
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
