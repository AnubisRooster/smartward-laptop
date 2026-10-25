import { useState } from 'react';
import { ago, del, errText, post, put } from '../api';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Empty, Err, Field, Modal, Spin, Title, inputCls, cx } from '../ui';
import { toast } from '../feedback';

const TONE: Record<string, 'green' | 'amber' | 'red' | 'indigo' | 'zinc'> = { emerging: 'indigo', rising: 'green', cooling: 'amber', steady: 'zinc', quiet: 'zinc', unknown: 'zinc' };
const WORDS: Record<string, string> = { emerging: 'Emerging', rising: 'Rising', cooling: 'Cooling', steady: 'Steady', quiet: 'Quiet', unknown: 'Not enough history' };
const STAGE: Record<string, string> = { paper: 'paper', release: 'release', lab: 'lab announcement', blog: 'commentary' };

/** Eight weekly bars, oldest to newest: the shape of attention on a domain. */
function Spark({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  return <svg viewBox="0 0 80 24" className="h-6 w-20" role="img" aria-label={`Articles per week, oldest to newest: ${values.join(', ')}`}>
    {values.map((v, i) => <rect key={i} x={i * 10 + 1} y={24 - (v / max) * 22 - 1} width="8" height={Math.max(1, (v / max) * 22)} rx="1" className={i >= values.length - 2 ? 'fill-indigo-400' : 'fill-zinc-600'} />)}
  </svg>;
}

export default function Radar() {
  const { data, error, loading, reload } = useLoad<any>('/signals', undefined, 120000);
  const { openArticle, go } = useNav(); const [editing, setEditing] = useState(false);
  const titles = data?.articles || {};
  const evidence = (ids: number[]) => (
    <ul className="mt-1 space-y-0.5">{ids.slice(0, 3).map(id => titles[id] && <li key={id} className="truncate text-xs"><button className="text-left text-indigo-300 hover:underline" onClick={() => openArticle(id)}>{titles[id].title}</button> <span className="text-zinc-500">· {titles[id].source} · {ago(titles[id].published)}</span></li>)}</ul>);
  const themeRow = (x: any) => (
    <li key={x.theme_id} className="rounded-lg border border-zinc-800 p-2">
      <div className="flex flex-wrap items-center gap-2 text-sm"><button className="font-medium hover:underline" onClick={() => go('graph', { themeId: x.theme_id })}>{x.name}</button><Badge>{x.type}</Badge>
        <span className="text-xs text-zinc-500">{x.recent} recent vs {x.baseline} before · {x.sources} source{x.sources === 1 ? '' : 's'} ({x.source_kinds.map((k: string) => STAGE[k]).join(', ')})</span></div>
      {x.ladder.stages.length > 1 && <div className="mt-1 text-xs text-zinc-500">Path so far: {x.ladder.stages.map((s: any) => STAGE[s.stage]).join(' → ')}{x.ladder.next ? ` · not yet seen as ${STAGE[x.ladder.next]}` : ''}</div>}
      {evidence(x.evidence)}
    </li>);
  return (
    <div className="h-full overflow-y-auto"><div className="mx-auto max-w-3xl space-y-4 p-5">
      <Title right={<><Btn small onClick={() => setEditing(true)}>Edit domains</Btn><Btn small onClick={reload}>↻ Refresh</Btn></>}>Radar</Title>
      <p className="text-sm text-zinc-500">What is rising, new or fading in the domains you follow, counted from your own articles. Each source is compared with its own past, so a feed you added recently can’t fake a trend. These are signals, not conclusions: open the evidence.</p>
      <Err>{error}</Err>
      {loading && !data && <div className="py-10 text-center"><Spin /></div>}
      {data?.domains?.[0]?.coverage?.provisional && <Card className="border-amber-700/50 text-sm text-amber-200">Provisional: only {data.domains[0].coverage.sources_comparable} sources have enough history to compare yet. The picture firms up as more weeks arrive.</Card>}
      {data?.domains?.length === 0 && <Empty icon="📡" title="No domains yet">Add a domain with a few keywords to start.</Empty>}
      {(data?.domains || []).map((d: any) => {
        const m = d.momentum; const any_ = d.emerging.length + d.rising.length + d.cooling.length + d.converging.length > 0;
        return (
          <Card key={d.domain} className="space-y-3">
            <div className="flex flex-wrap items-center gap-3"><h2 className="text-base font-semibold">{d.domain}</h2><Badge tone={TONE[m.label]}>{WORDS[m.label]}</Badge><span className="ml-auto"><Spark values={d.weekly} /></span></div>
            <div className="text-xs text-zinc-500">{m.recent} articles in the last {d.window.recent_days} days, {m.baseline} in the {d.window.baseline_days} before.{m.label !== 'unknown' && <> Compared fairly across sources: {m.observed_comparable} seen, {m.expected} expected from each source’s own history.</>}</div>
            {!any_ && <div className="text-sm text-zinc-500">No themes stand out yet. Themes come from articles that have been read for entities; {d.evidence.length ? 'newer articles are still being processed.' : 'nothing matches this domain’s keywords recently.'}</div>}
            {(['emerging', 'rising', 'cooling'] as const).map(k => d[k].length > 0 && (
              <div key={k}><h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">{WORDS[k]}</h3><ul className="space-y-1.5">{d[k].map(themeRow)}</ul></div>))}
            {d.converging.length > 0 && <div><h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">Converging</h3>
              <ul className="space-y-1.5">{d.converging.map((x: any) => <li key={x.a_id + '-' + x.b_id} className="rounded-lg border border-zinc-800 p-2 text-sm"><span className="font-medium">{x.a}</span> + <span className="font-medium">{x.b}</span> <span className="text-xs text-zinc-500">appeared together {x.together}× recently, never before{x.bridge ? ' · links two separate clusters' : ''}</span>{evidence(x.evidence)}</li>)}</ul></div>}
          </Card>);
      })}
      {editing && <DomainEditor domains={(data?.domains || []).map((d: any) => d.domain)} onClose={() => { setEditing(false); reload(); }} />}
    </div></div>
  );
}

function DomainEditor({ onClose }: { domains: string[]; onClose: () => void }) {
  const { data, reload } = useLoad<any[]>('/domains');
  const [name, setName] = useState(''); const [kws, setKws] = useState(''); const [err, setErr] = useState('');
  const parse = (t: string) => t.split(/[\n,]/).map(x => x.trim()).filter(Boolean);
  const add = async () => { setErr(''); try { await post('/domains', { name, keywords: parse(kws) }); setName(''); setKws(''); reload(); } catch (e) { setErr(errText(e)); } };
  return (
    <Modal title="Domains you follow" onClose={onClose} wide>
      <div className="space-y-3 text-sm">
        <p className="text-xs text-zinc-500">A domain is a name and the words that mean an article belongs to it (whole words, any case). Changes show on the Radar straight away.</p>
        <ul className="max-h-72 space-y-2 overflow-y-auto">{(data || []).map(d => <DomainRow key={d.id} d={d} onChanged={reload} />)}</ul>
        <Err>{err}</Err>
        <div className="space-y-2 rounded-lg border border-zinc-800 p-3"><Field label="New domain"><input className={inputCls} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Robotics" /></Field>
          <Field label="Keywords (comma or new line)"><textarea className={inputCls} rows={2} value={kws} onChange={e => setKws(e.target.value)} placeholder="robot, manipulation, embodied" /></Field>
          <Btn kind="primary" onClick={add} disabled={!name.trim() || !parse(kws).length}>Add domain</Btn></div>
        <div className="flex justify-end"><Btn onClick={onClose}>Done</Btn></div>
      </div>
    </Modal>
  );
}

function DomainRow({ d, onChanged }: { d: any; onChanged: () => void }) {
  const [text, setText] = useState(d.keywords.join(', ')); const dirty = text !== d.keywords.join(', ');
  const save = async () => { try { await put(`/domains/${d.id}`, { keywords: text.split(/[\n,]/).map((x: string) => x.trim()).filter(Boolean) }); onChanged(); toast.ok('Saved'); } catch (e) { toast.error(errText(e)); } };
  return (
    <li className="rounded-lg border border-zinc-800 p-2"><div className="mb-1 flex items-center justify-between"><span className="font-medium">{d.name}</span>
      <Btn small kind="ghost" onClick={async () => { await del(`/domains/${d.id}`); onChanged(); }}>Remove</Btn></div>
      <textarea className={cx(inputCls, 'text-xs')} rows={2} value={text} onChange={e => setText(e.target.value)} aria-label={`Keywords for ${d.name}`} />
      {dirty && <div className="mt-1 flex justify-end"><Btn small kind="primary" onClick={save}>Save keywords</Btn></div>}</li>
  );
}
