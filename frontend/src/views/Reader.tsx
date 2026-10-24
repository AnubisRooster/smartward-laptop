import { useEffect, useMemo, useState } from 'react';
import { get, patch, post, errText } from '../api';
import { speech, useNav, useSpeech } from '../hooks';
import { Badge, Btn, Card, Err, Spin } from '../ui';

export default function Reader({ id, onBack, onChanged }: { id: number; onBack: () => void; onChanged: () => void }) {
  const [a, setA] = useState<any>(null); const [err, setErr] = useState(''); const [sumBusy, setSumBusy] = useState(false);
  const sp = useSpeech(); const { go } = useNav();
  const load = async () => { try { const r = await get(`/articles/${id}`); setA(r); setErr(''); if (!r.read) { patch(`/articles/${id}`, { read: true }).then(onChanged); } return r; } catch (e) { setErr(errText(e)); } };
  useEffect(() => { setA(null); load().then(r => { if (r && !r.summary && r.relevant !== undefined) summarize(false); }); return () => { speech.stop(); }; }, [id]);

  const summarize = async (force: boolean) => {
    setSumBusy(true);
    try { const s = await post(`/articles/${id}/summary?force=${force}`); setA((x: any) => x && { ...x, summary: s, has_summary: true }); setErr(''); }
    catch (e) { setErr(errText(e)); }
    setSumBusy(false);
  };
  const paras = useMemo(() => (a?.text || '').split(/\n{1,}/).map((s: string) => s.trim()).filter(Boolean), [a?.text]);
  const sumParts = (): string[] => a?.summary ? a.summary_keys.flatMap(([k, l]: [string, string]) => (a.summary[k] || []).length ? [l + '.', ...a.summary[k]] : []) : [];
  const head = () => [a.title, `${a.source}.`];
  const readAll = async () => { const rate = (await get('/settings')).voice_rate || 1; speech.speak([...head(), ...sumParts(), ...(a.themes.length ? ['Themes: ' + a.themes.map((t: any) => t.name).join(', ')] : []), ...paras], rate); };
  const readSummary = async () => { const rate = (await get('/settings')).voice_rate || 1; speech.speak([...head(), ...sumParts()], rate); };
  const loadFull = async () => { try { await post(`/articles/${id}/full`); setTimeout(load, 2500); } catch (e) { setErr(errText(e)); } };

  if (!a) return <div className="p-6">{err ? <Err>{err}</Err> : <Spin />}</div>;
  const short = !a.full_text && (a.text || '').length < 900;

  return (
    <article className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl px-5 py-4">
        <div className="mb-3 flex items-center justify-between"><button className="text-sm text-zinc-400 hover:text-white md:hidden" onClick={onBack}>← Back</button><span className="hidden md:block" />
          <div className="flex gap-1.5">
            <Btn small onClick={async () => { await patch(`/articles/${id}`, { starred: !a.starred }); load(); onChanged(); }}>{a.starred ? '★ Starred' : '☆ Star'}</Btn>
            <Btn small onClick={async () => { await patch(`/articles/${id}`, { read: !a.read }); load(); onChanged(); }}>{a.read ? 'Mark unread' : 'Mark read'}</Btn>
            <a href={a.url} target="_blank" rel="noreferrer" className="inline-flex items-center rounded-lg border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-xs hover:bg-zinc-700">Open original ↗</a></div></div>
        <h1 className="text-2xl font-semibold leading-tight">{a.title}</h1>
        <div className="mt-1 text-sm text-zinc-500">{a.source}{a.author ? ` · ${a.author}` : ''}{a.published ? ` · ${new Date(a.published * 1000).toLocaleDateString()}` : ''}{a.relevance != null && ` · ${Math.round(a.relevance * 100)}% relevant`}</div>

        {speech.supported && (
          <div className="my-3 flex flex-wrap items-center gap-1.5" role="group" aria-label="Read aloud">
            {!sp.on ? <><Btn small onClick={readAll}>🔊 Read aloud</Btn><Btn small onClick={readSummary}>🔊 Summary only</Btn></> :
              <><Btn small onClick={() => sp.paused ? sp.resume() : sp.pause()}>{sp.paused ? '▶ Keep going' : '⏸ Pause'}</Btn><Btn small onClick={() => sp.skip(-1)}>⏮ Back</Btn><Btn small onClick={() => sp.skip(1)}>⏭ Skip</Btn><Btn small onClick={() => sp.stop()}>■ Stop</Btn></>}
            {sp.notice && <span className="basis-full text-xs text-amber-500">{sp.notice}</span>}
            <span className="text-xs text-zinc-600">Read aloud on this computer — text never leaves it.</span></div>)}

        <Card className="my-4">
          <div className="mb-2 flex items-center justify-between"><div className="text-sm font-semibold">Summary</div>
            <div className="flex items-center gap-2">{sumBusy && <><Spin /><span className="text-xs text-zinc-500">Writing…</span></>}{a.summary && !sumBusy && <button className="text-xs text-zinc-500 hover:text-zinc-300" onClick={() => summarize(true)}>Redo</button>}</div></div>
          {a.summary ? (<dl className="space-y-3">{a.summary_keys.map(([k, l]: [string, string]) => (a.summary[k] || []).length > 0 && (
            <div key={k}><dt className="text-xs font-medium uppercase tracking-wide text-indigo-300">{l}</dt>{a.summary[k].map((b: string, i: number) => <dd key={i} className="mt-0.5 text-sm text-zinc-300">• {b}</dd>)}</div>))}</dl>)
            : !sumBusy && <div className="text-sm text-zinc-500">No summary yet. <button className="text-indigo-400 underline" onClick={() => summarize(false)}>Write one</button></div>}
        </Card>

        {a.themes?.length > 0 && <div className="mb-4 flex flex-wrap items-center gap-1.5"><span className="text-xs text-zinc-500">Themes</span>{a.themes.map((t: any) => <button key={t.id} onClick={() => go('graph', { themeId: t.id })}><Badge tone="indigo">{t.name}</Badge></button>)}</div>}
        <Err>{err}</Err>
        {a.stage_error && <div className="mb-2 text-xs text-amber-500">Note: {a.stage_error}</div>}
        {short && <Card className="mb-4 text-sm text-zinc-400">Only the headline and a short teaser were saved. <button className="text-indigo-400 underline" onClick={loadFull}>Load the full article</button></Card>}
        <div className="prose-sw">{paras.map((p: string, i: number) => <p key={i} className={sp.on && sp.queue[sp.idx] === p ? 'speaking' : ''}>{p}</p>)}</div>
      </div>
    </article>
  );
}
