import { useState } from 'react';
import { errText, get, http, post } from '../api';
import { speech, useLoad, useNav, useSpeech } from '../hooks';
import { briefParts } from '../digestBrief';
import { Badge, Btn, Card, Empty, Err, Spin, Title } from '../ui';

export default function Today() {
  const { data, loading, error, reload, setData } = useLoad<any>('/digest');
  const { go, openArticle } = useNav(); const sp = useSpeech();
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const rebuild = async () => { setBusy(true); setErr(''); try { setData(await http.get('/digest', { params: { rebuild: true }, timeout: 300000 }).then(r => r.data)); } catch (e) { setErr(errText(e)); } setBusy(false); };

  const brief = async () => { const rate = (await get('/settings')).voice_rate || 1; speech.speak(briefParts(data?.clusters || []), rate, '', 'today'); };

  const clusters: any[] = data?.clusters || [];
  return (
    <div className="h-full overflow-y-auto"><div className="mx-auto max-w-3xl p-5">
      <Title right={<>{speech.supported && (sp.on && sp.owner === 'today' ? <Btn onClick={() => speech.stop()}>■ Stop</Btn> : <Btn onClick={brief} disabled={loading || clusters.length === 0} title="Reads the themes shown below">🔊 Brief me</Btn>)}<Btn onClick={rebuild} disabled={busy}>{busy ? <Spin /> : '↻'} Update</Btn></>}>Today</Title>
      <Err>{error || err}</Err>
      {loading && <div className="py-10 text-center"><Spin /></div>}
      {!loading && clusters.length === 0 && <Empty icon="☀" title="Nothing new yet">When articles are indexed they’re grouped by theme here, ranked by how much they touch your projects.
        <div className="mt-3"><Btn onClick={() => go('reading', { sources: true })}>Add sources</Btn></div></Empty>}
      {data?.created && clusters.length > 0 && <div className="mb-3 text-xs text-zinc-500">{data.count} new articles since the last digest · built {new Date(data.created * 1000).toLocaleString()}</div>}
      <div className="space-y-3">{clusters.map((c, i) => (
        <Card key={c.theme_id}>
          <div className="mb-1 flex items-center gap-2"><h2 className="font-medium">{c.theme}</h2>{c.touches_project && <Badge tone="green">Touches your projects</Badge>}<Badge>{c.article_ids.length} article{c.article_ids.length === 1 ? '' : 's'}</Badge>
            <button className="ml-auto text-xs text-zinc-500 hover:text-zinc-200" onClick={() => go('graph', { themeId: c.theme_id })}>Theme →</button></div>
          {c.summary && <p className="mb-2 text-sm text-zinc-400">{c.summary}</p>}
          <ul className="space-y-1">{c.articles.map((a: any) => <li key={a.id}><button className="text-left text-sm text-indigo-300 hover:underline" onClick={() => openArticle(a.id)}>{a.title}</button></li>)}</ul></Card>))}</div>
    </div></div>
  );
}
