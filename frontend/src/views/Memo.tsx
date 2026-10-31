import { useEffect, useState } from 'react';
import { ago, errText, get, post } from '../api';
import { memoParts } from '../digestBrief';
import { speech, useLoad, useNav, useSpeech } from '../hooks';
import { Badge, Btn, Card, Err } from '../ui';
import ShareButtons from './ShareButtons';

const VERDICT: Record<string, [string, 'green' | 'red' | 'zinc']> = { supported: ['Supported so far', 'green'], contradicted: ['Contradicted so far', 'red'], open: ['Still open', 'zinc'] };
const HEADS: [string, string][] = [['shifted', 'What shifted'], ['projects', 'What it may mean for your projects'], ['watch', 'What to watch next week'], ['questions', 'Open questions']];

/** The weekly strategy memo, on top of the Radar: each point cites the developments it rests on. */
export default function MemoCard() {
  const { data, reload } = useLoad<any>('/memos');
  const { openArticle, go } = useNav(); const sp = useSpeech();
  const [picked, setPicked] = useState<any>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  useEffect(() => { setPicked(null); }, [data?.latest?.id]);
  const m = picked || data?.latest;

  const write = async () => {
    setBusy(true); setErr('');
    try {
      await post('/memo/run');
      for (let i = 0; i < 150; i++) { await new Promise(r => setTimeout(r, 2000)); const st = await get('/memo/status'); if (!st.running) { if (st.last?.error) setErr(st.last.error); break; } }
      await reload();
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  const read = async () => { const rate = (await get('/settings')).voice_rate || 1; speech.speak(memoParts(m), rate, '', 'memo'); };
  const pick = async (id: number) => { try { setPicked(id === data?.latest?.id ? null : await get(`/memos/${id}`)); } catch (e) { setErr(errText(e)); } };

  const cites = (ids: number[]) => ids.length > 0 && (
    <span className="ml-1 text-xs text-zinc-500">{ids.map((id, i) => { const c = m.citations[String(id)]; return c && <span key={id}>{i > 0 && ' · '}<button className="text-indigo-300 hover:underline" title={c.claim} onClick={() => openArticle(c.article_id)}>{c.source}</button>{c.evidence === 'measured' && <span title="A measured result"> ●</span>}</span>; })}</span>);

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">Weekly memo</h2>
        {m && <span className="text-xs text-zinc-500">week {m.week.split('-W')[1]} · written {ago(m.created)}</span>}
        <span className="ml-auto flex flex-wrap gap-2">
          {(data?.memos?.length || 0) > 1 && <select aria-label="Earlier memos" className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs" value={m?.id} onChange={e => pick(Number(e.target.value))}>
            {data.memos.map((x: any) => <option key={x.id} value={x.id}>Week {x.week.split('-W')[1]}, {x.week.split('-W')[0]}</option>)}</select>}
          {m && <ShareButtons kind="memo" id={m.id} />}
          {m && speech.supported && (sp.on && sp.owner === 'memo' ? <Btn small onClick={() => speech.stop()}>■ Stop</Btn> : <Btn small onClick={read} title="Reads this memo aloud">🔊 Read aloud</Btn>)}
          {<Btn small onClick={write} loading={busy} title="Checks accepted implications, then writes this week's memo from the week's checked developments">{m && m.week === data?.latest?.week && !picked ? 'Rewrite' : 'Write this week’s memo'}</Btn>}
        </span>
      </div>
      <Err>{err}</Err>
      {!m && !busy && <p className="text-sm text-zinc-500">No memo yet. {'Write one to see what shifted this week and what it may mean for your projects. To have it written every week, turn it on in Settings → Background refresh.'}</p>}
      {busy && <p className="text-sm text-zinc-500" role="status">Checking how accepted implications are holding up, then writing the memo. Free models can take a few minutes.</p>}
      {m && <>
        {HEADS.map(([k, head]) => m[k]?.length > 0 && (
          <div key={k}><h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">{head}</h3>
            <ul className="space-y-1.5">{m[k].map((p: any, i: number) => (
              <li key={i} className="text-sm text-zinc-300">{p.project && <button className="mr-1 font-medium text-zinc-100 hover:underline" onClick={() => go('projects', { projectId: p.project_id })}>{p.project}:</button>}
                {p.text}{p.caution && <Badge tone="amber">strong wording, thin evidence</Badge>}{cites(p.evidence)}</li>))}</ul></div>))}
        {m.standing?.length > 0 && <div><h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">How accepted implications are holding up</h3>
          <ul className="space-y-1">{m.standing.map((s: any) => <li key={s.id} className="flex flex-wrap items-center gap-2 text-sm"><Badge tone={VERDICT[s.verdict]?.[1]}>{VERDICT[s.verdict]?.[0] || s.verdict}</Badge>{s.headline}<span className="text-xs text-zinc-500">· {s.project}</span></li>)}</ul></div>}
        <p className="text-xs text-zinc-500">From {m.considered} checked developments. Points without real evidence are left out{m.dropped ? ` (${m.dropped} this time)` : ''}.
          {(m.left_out?.private_articles || m.left_out?.private_projects) ? ` Private material is never included: ${m.left_out.private_articles} private article${m.left_out.private_articles === 1 ? '' : 's'} and ${m.left_out.private_projects} project${m.left_out.private_projects === 1 ? '' : 's'} with private links were left out.` : ''} ● marks a measured result.</p>
      </>}
    </Card>
  );
}
