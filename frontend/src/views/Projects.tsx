import { useState } from 'react';
import { ago, del, errText, get, patch, post, put } from '../api';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Empty, Err, Field, inputCls, Modal, Spin, Title, cx } from '../ui';
import { ask, toast } from '../feedback';
import { AddSource } from './Sources';
import ShareButtons from './ShareButtons';
import ProjectMap from './ProjectMap';
import { TestThis } from './Bench';

export default function Projects() {
  const { projectId, go } = useNav();
  const { data: list, reload } = useLoad<any[]>('/projects', undefined, 6000);
  const [adding, setAdding] = useState(false);
  return (
    <div className="flex h-full">
      <section className={cx('flex min-h-0 w-full flex-col border-zinc-800 md:w-80 md:shrink-0 md:border-r', projectId != null && 'hidden md:flex')}>
        <div className="flex items-center justify-between border-b border-zinc-800 p-3"><h1 className="text-lg font-semibold">Projects</h1><Btn small kind="primary" onClick={() => setAdding(true)}>+ New</Btn></div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {(list || []).length === 0 && <Empty icon="▣" title="No projects yet">A project holds a goal, a brief, decisions and open questions. The strategist and your reading both work from it.</Empty>}
          {(list || []).map(p => (
            <div key={p.id} role="button" tabIndex={0} onClick={() => go('projects', { projectId: p.id })} onKeyDown={e => e.key === 'Enter' && go('projects', { projectId: p.id })} className={cx('cursor-pointer border-b border-zinc-800/70 px-4 py-3 hover:bg-zinc-900', projectId === p.id && 'bg-zinc-900')}>
              <div className="flex items-center gap-2"><span className="truncate text-sm font-medium">{p.name}</span>{p.has_suggestion && <Badge tone="indigo">Suggestion</Badge>}</div>
              <div className="truncate text-xs text-zinc-500">{p.goal}</div><div className="text-xs text-zinc-600">{p.open_items} open · {ago(p.updated)}</div></div>))}
        </div>
      </section>
      <section className={cx('min-w-0 flex-1', projectId == null && 'hidden md:block')}>
        {projectId != null ? <Project id={projectId} onBack={() => go('projects', { projectId: null })} onChanged={reload} /> : <div className="hidden h-full items-center justify-center md:flex"><Empty icon="▣" title="Pick a project" /></div>}
      </section>
      {adding && <NewProject onClose={() => setAdding(false)} onCreated={id => { setAdding(false); reload(); go('projects', { projectId: id }); }} />}
    </div>
  );
}

function NewProject({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const [name, setName] = useState(''); const [goal, setGoal] = useState(''); const [err, setErr] = useState('');
  const go = async () => { try { const r = await post('/projects', { name, goal, brief: goal }); onCreated(r.id); } catch (e) { setErr(errText(e)); } };
  return <Modal title="New project" onClose={onClose}><div className="space-y-3"><Field label="Name"><input className={inputCls} value={name} onChange={e => setName(e.target.value)} autoFocus /></Field>
    <Field label="Goal"><textarea className={inputCls} rows={3} value={goal} onChange={e => setGoal(e.target.value)} /></Field><Err>{err}</Err>
    <div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" disabled={!name.trim()} onClick={go}>Create</Btn></div></div></Modal>;
}

const ITEMS_OPEN = 'sw.project.items.open';     // whether "Decisions, questions & actions" is open, for every project

/** An item's text, cut to three lines when it is long (saved architecture copies run to pages), with Show all / Show less. */
function ItemText({ text, done }: { text: string; done: boolean }) {
  const [all, setAll] = useState(false);
  const long = text.length > 280 || text.split('\n').length > 3;
  return <div className={cx('min-w-0 flex-1 text-sm', done && 'text-zinc-500 line-through')}>
    <div className={cx('whitespace-pre-wrap break-words', long && !all && 'line-clamp-3')}>{text}</div>
    {long && <button className="text-xs text-indigo-300 hover:underline" onClick={() => setAll(!all)}>{all ? 'Show less' : 'Show all'}</button>}</div>;
}

function Project({ id, onBack, onChanged }: { id: number; onBack: () => void; onChanged: () => void }) {
  const { data: p, error, reload } = useLoad<any>(`/projects/${id}`, undefined, 7000);
  const { go, openArticle } = useNav();
  const [editing, setEditing] = useState(false); const [brief, setBrief] = useState(''); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const [newItem, setNewItem] = useState({ kind: 'action', text: '' }); const [link, setLink] = useState(''); const [addSrc, setAddSrc] = useState(false); const [hist, setHist] = useState(false);
  const [itemsOpen, setItemsOpen] = useState(() => { try { return localStorage.getItem(ITEMS_OPEN) !== '0'; } catch { return true; } });
  const showItems = (v: boolean) => { setItemsOpen(v); try { localStorage.setItem(ITEMS_OPEN, v ? '1' : '0'); } catch { /* the choice just isn't remembered */ } };
  if (error) return <div className="p-4"><Err>{error}</Err></div>;
  if (!p) return <div className="p-6"><Spin /></div>;
  const run = async (fn: () => Promise<any>) => { setErr(''); setBusy(true); try { await fn(); await reload(); onChanged(); } catch (e) { setErr(errText(e)); } setBusy(false); };
  const KIND: Record<string, string> = { decision: 'Decisions', question: 'Open questions', action: 'Action items' };
  return (
    <div className="h-full overflow-y-auto"><div className="mx-auto max-w-3xl space-y-4 p-5">
      <div className="flex items-start justify-between gap-2"><div><button className="mb-1 text-sm text-zinc-400 md:hidden" onClick={onBack}>← Projects</button><h1 className="text-xl font-semibold">{p.name}</h1><div className="text-sm text-zinc-400">{p.goal}</div></div>
        <div className="flex gap-1.5"><Btn small onClick={() => go('chat', { projectId: id })}>✎ Chat about this</Btn><Btn small kind="danger" onClick={async () => { if (await ask.confirm({ title: 'Delete this project?', body: 'Its brief, decisions, questions, actions and links are removed. Articles stay in your library.', confirmLabel: 'Delete', danger: true })) { await del(`/projects/${id}`); onChanged(); onBack(); } }}>Delete</Btn></div></div>
      <Err>{err}</Err>

      <Card>
        <div className="mb-2 flex items-center justify-between"><h2 className="font-medium">Brief</h2><div className="flex gap-1.5">
          {!editing && <><Btn small onClick={() => run(() => post(`/projects/${id}/suggest`))} disabled={busy}>{busy ? <Spin /> : '✨'} Suggest an update</Btn><Btn small onClick={() => { setBrief(p.brief); setEditing(true); }}>Edit</Btn>{p.history.length > 0 && <Btn small kind="ghost" onClick={() => setHist(true)}>History ({p.history.length})</Btn>}</>}</div></div>
        {editing ? <><textarea className={inputCls} rows={8} value={brief} onChange={e => setBrief(e.target.value)} /><div className="mt-2 flex justify-end gap-2"><Btn small onClick={() => setEditing(false)}>Cancel</Btn><Btn small kind="primary" onClick={() => run(async () => { await put(`/projects/${id}`, { brief }); setEditing(false); })}>Save</Btn></div></>
          : <div className="whitespace-pre-wrap text-sm text-zinc-300">{p.brief || <span className="text-zinc-500">No brief yet.</span>}</div>}
        {p.suggestion && <div className="mt-3 rounded-lg border border-indigo-800 bg-indigo-950/30 p-3"><div className="mb-1 text-sm font-medium text-indigo-200">Suggested update <span className="font-normal text-zinc-400">(+{p.suggestion.added} −{p.suggestion.removed} lines)</span></div>
          <div className="mb-2 text-xs text-zinc-400">{p.suggestion.reason}</div>
          <pre className="mb-2 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-zinc-950 p-2 text-xs">{p.suggestion.diff.map((d: any, i: number) => <div key={i} className={d.op === 'add' ? 'bg-emerald-900/40 text-emerald-200' : d.op === 'del' ? 'bg-red-900/40 text-red-200 line-through' : 'text-zinc-500'}>{d.op === 'add' ? '+ ' : d.op === 'del' ? '− ' : '  '}{d.text}</div>)}</pre>
          <div className="flex gap-2"><Btn small kind="primary" onClick={() => run(() => post(`/projects/${id}/suggestion/accept`))}>Accept</Btn><Btn small onClick={() => run(() => post(`/projects/${id}/suggestion/reject`))}>Reject</Btn></div></div>}
      </Card>

      <Card><button className="flex w-full items-center gap-2 text-left" aria-expanded={itemsOpen} onClick={() => showItems(!itemsOpen)}>
          <span className={cx('text-xs text-zinc-500 transition-transform', itemsOpen && 'rotate-90')}>▶</span><h2 className="font-medium">Decisions, questions & actions</h2>
          {!itemsOpen && <span className="ml-auto text-xs text-zinc-500">{['decision', 'question', 'action'].map(k => `${p.items.filter((i: any) => i.kind === k && !i.done).length} ${KIND[k].toLowerCase()}`).join(' · ')}</span>}</button>
        {itemsOpen && <div className="mt-2">
        {['decision', 'question', 'action'].map(k => { const its = p.items.filter((i: any) => i.kind === k); return its.length > 0 && (
          <div key={k} className="mb-3"><div className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">{KIND[k]}</div>
            {its.map((i: any) => (<div key={i.id} className="group flex items-start gap-2 py-0.5"><input type="checkbox" aria-label={`${k}: ${i.text}`} className="mt-1" checked={!!i.done} onChange={() => run(() => patch(`/items/${i.id}`, { done: !i.done }))} />
              <ItemText text={i.text} done={!!i.done} /><button className="text-xs text-zinc-600 opacity-0 group-hover:opacity-100 focus:opacity-100 pointer-coarse:opacity-100 hover:text-red-400" onClick={() => run(() => del(`/items/${i.id}`))}>✕</button></div>))}</div>); })}
        <form className="flex gap-2" onSubmit={e => { e.preventDefault(); if (newItem.text.trim()) run(async () => { await post(`/projects/${id}/items`, newItem); setNewItem({ ...newItem, text: '' }); }); }}>
          <select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 text-sm" value={newItem.kind} onChange={e => setNewItem({ ...newItem, kind: e.target.value })}><option value="decision">Decision</option><option value="question">Question</option><option value="action">Action</option></select>
          <input className={inputCls} value={newItem.text} onChange={e => setNewItem({ ...newItem, text: e.target.value })} placeholder="Add…" /><Btn type="submit">Add</Btn></form></div>}</Card>

      <Card><div className="mb-2 flex items-center justify-between"><h2 className="font-medium">Links</h2><Btn small onClick={() => setAddSrc(true)}>+ Follow a source for this project</Btn></div>
        {p.links.map((l: any) => (<div key={l.id} className="flex items-center gap-2 py-1 text-sm"><Badge>{l.kind}</Badge>{l.private ? <Badge tone="amber">Private</Badge> : null}
          <button className="min-w-0 flex-1 truncate text-left text-indigo-300 hover:underline" title="Edit link" onClick={async () => { const u = await ask.prompt({ title: 'Edit link', label: 'Link', initial: l.url, confirmLabel: 'Save' }); if (u && u.trim() && u !== l.url) run(() => put(`/links/${l.id}`, { url: u.trim() })); }}>{l.url}</button>
          {l.kind === 'github' && <Btn small onClick={() => run(() => post(`/links/${l.id}/sync`))}>Sync docs</Btn>}{l.note && <span className="text-xs text-zinc-500">{l.note}</span>}<button className="text-zinc-600 hover:text-red-400" onClick={() => run(() => del(`/links/${l.id}`))}>✕</button></div>))}
        <form className="mt-2 flex gap-2" onSubmit={e => { e.preventDefault(); if (link.trim()) run(async () => { await post(`/projects/${id}/links`, { url: link }); setLink(''); }); }}>
          <input className={inputCls} value={link} onChange={e => setLink(e.target.value)} placeholder="https://… or https://github.com/owner/repo" /><Btn type="submit">Add link</Btn></form>
        <div className="mt-1 text-xs text-zinc-500">GitHub links sync docs and manifests read-only; SmartWard never writes back. Private repo content stays on this device. For private repos add a token in Settings.</div></Card>

      <ProjectMap pid={id} />

      <Implications pid={id} onAccepted={() => { reload(); onChanged(); }} />

      <Card><h2 className="mb-2 font-medium">Related reading</h2>
        {p.related.length === 0 ? <div className="text-sm text-zinc-500">Nothing yet. Articles show up here when they’re shared to this project, cover its themes, or name one of its pinned tools.</div> :
          <ul className="space-y-2">{p.related.map((a: any) => <li key={a.id}><button className="text-left text-sm text-indigo-300 hover:underline" onClick={() => openArticle(a.id)}>{a.title}</button><div className="text-xs text-zinc-500">{a.reason}</div></li>)}</ul>}</Card>

      {addSrc && <AddSource projectId={id} onClose={() => setAddSrc(false)} />}
      {hist && <Modal title="Brief history" onClose={() => setHist(false)} wide>{p.history.map((h: any) => <div key={h.id} className="flex items-center justify-between border-b border-zinc-800 py-2 text-sm"><div><div>{h.note}</div><div className="text-xs text-zinc-500">{new Date(h.ts * 1000).toLocaleString()}</div></div>
        <Btn small onClick={() => run(async () => { await post(`/projects/${id}/restore/${h.id}`); setHist(false); })}>Restore this version</Btn></div>)}</Modal>}
    </div></div>
  );
}


const STANDING: Record<string, [string, 'green' | 'red' | 'zinc']> = { supported: ['Holding up so far', 'green'], contradicted: ['Contradicted since', 'red'], open: ['Still open', 'zinc'] };
const DIRECTION: Record<string, [string, 'green' | 'red' | 'indigo' | 'zinc']> = { accelerates: ['Could speed this up', 'green'], threatens: ['Could undercut part of this', 'red'], enables: ['Could open something new', 'indigo'], neutral: ['Worth knowing', 'zinc'] };

/** What recent developments might mean for this project: hypotheses with their evidence, for you to accept into the project or dismiss. */
function Implications({ pid, onAccepted }: { pid: number; onAccepted: () => void }) {
  const { data, reload } = useLoad<any>(`/projects/${pid}/implications`);
  const { openArticle } = useNav(); const [busy, setBusy] = useState(false); const [note, setNote] = useState('');
  const look = async () => {
    setBusy(true); setNote('');
    try {
      await post(`/projects/${pid}/implications/run`);
      for (let i = 0; i < 90; i++) { await new Promise(r => setTimeout(r, 2000)); const st = await get('/implications/status'); if (!st.running) { const l = st.last || {}; setNote(l.error || l.message || `${l.new || 0} new, ${l.updated || 0} updated from ${l.evidence || 0} developments.`); break; } }
      await reload();
    } catch (e) { setNote(errText(e)); }
    setBusy(false);
  };
  const act = async (fn: () => Promise<any>, accepted = false) => { try { await fn(); await reload(); if (accepted) onAccepted(); } catch (e) { toast.error(errText(e)); } };
  const rows: any[] = data?.hypotheses || []; const cites = data?.citations || {};
  const open = rows.filter(r => r.status === 'new'), done = rows.filter(r => r.status !== 'new');
  const cite = (id: number, counter = false) => { const c = cites[id]; return c && <li key={id} className="text-xs"><span className={counter ? 'text-amber-400' : 'text-zinc-400'}>{c.evidence}</span> · {c.claim} <button className="text-indigo-300 hover:underline" onClick={() => openArticle(c.article_id)}>{c.source}</button>{c.source !== 'Test bench' && <TestThis devId={c.id} />}{c.quote && <span className="block text-zinc-500">“{c.quote}”</span>}</li>; };
  const card = (r: any) => (
    <li key={r.id} className="rounded-lg border border-zinc-800 p-3">
      <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{r.headline}</span><Badge tone={DIRECTION[r.direction]?.[1]}>{DIRECTION[r.direction]?.[0] || r.direction}</Badge><Badge>{r.confidence} confidence</Badge>
        {r.status === 'accepted' && <Badge tone="green">Added to actions</Badge>}{r.standing && <Badge tone={STANDING[r.standing.verdict]?.[1]}>{STANDING[r.standing.verdict]?.[0]}</Badge>}{r.status === 'dismissed' && <Badge>Dismissed{r.reason ? `: ${r.reason}` : ''}</Badge>}</div>
      <p className="mt-1 text-sm text-zinc-300">{r.implication}</p>
      {r.falsifier && <p className="mt-1 text-xs text-zinc-500"><span className="font-medium">What would change my mind:</span> {r.falsifier}</p>}
      {r.action && <p className="mt-1 text-xs text-zinc-500"><span className="font-medium">A small next step:</span> {r.action}</p>}
      <details className="mt-1"><summary className="cursor-pointer text-xs text-zinc-500">Evidence ({r.evidence.length}{r.counter.length ? `, ${r.counter.length} against` : ''})</summary>
        <ul className="mt-1 space-y-1">{r.evidence.map((i: number) => cite(i))}{r.counter.map((i: number) => cite(i, true))}</ul></details>
      {r.standing && (r.standing.supports.length + r.standing.contradicts.length) > 0 && <details className="mt-1"><summary className="cursor-pointer text-xs text-zinc-500">Since you accepted it: {r.standing.supports.length} for, {r.standing.contradicts.length} against · checked {ago(r.standing.checked)}</summary>
        <ul className="mt-1 space-y-1">{r.standing.supports.map((i: number) => cite(i))}{r.standing.contradicts.map((i: number) => cite(i, true))}</ul></details>}
      {r.status === 'new' && <div className="mt-2 flex gap-2"><Btn small kind="primary" onClick={() => act(() => post(`/implications/${r.id}/accept`), true)}>Add as an action</Btn>
        <Btn small onClick={async () => { const why = await ask.prompt({ title: 'Dismiss this?', body: 'Optionally say why, so it’s clear later.', label: 'Reason (optional)', confirmLabel: 'Dismiss' }); if (why !== null) act(() => post(`/implications/${r.id}/dismiss`, { reason: why })); }}>Dismiss</Btn></div>}
    </li>);
  return (
    <Card className="space-y-2">
      <div className="flex items-center justify-between gap-2"><div><h2 className="font-medium">Implications</h2><div className="text-xs text-zinc-500">Hypotheses from what you’ve been reading, each with its evidence. Not conclusions: you decide.</div></div>
        <div className="flex flex-wrap gap-2">{rows.some(r => r.status !== 'dismissed') && <ShareButtons kind="project" id={pid} />}<Btn small onClick={look} loading={busy}>Look for implications</Btn></div></div>
      {note && <div className="text-xs text-zinc-400" role="status">{note}</div>}
      {open.length === 0 && !busy && <div className="text-sm text-zinc-500">{rows.length ? 'Nothing new to review.' : 'None yet. Press “Look for implications” to check recent developments against this project.'}</div>}
      <ul className="space-y-2">{open.map(card)}</ul>
      {done.length > 0 && <details><summary className="cursor-pointer text-xs text-zinc-500">Reviewed ({done.length})</summary><ul className="mt-2 space-y-2">{done.map(card)}</ul></details>}
    </Card>
  );
}
