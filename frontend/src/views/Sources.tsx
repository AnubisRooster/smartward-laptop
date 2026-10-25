import { useState } from 'react';
import { del, errText, post, ago, patch } from '../api';
import { useLoad } from '../hooks';
import { Badge, Btn, Card, Empty, Err, Field, inputCls, Modal, Spin, Title } from '../ui';
import { ask, toast } from '../feedback';

const KINDS: [string, string, string][] = [
  ['rss', 'Blog / feed', 'A site’s RSS or Atom feed — or just its home page and SmartWard will look for the feed.'],
  ['arxiv', 'arXiv', 'A category like cs.CL or a search like “speculative decoding”.'],
  ['hf_papers', 'Hugging Face papers', 'Today’s daily papers.'],
  ['hn', 'Hacker News', 'Stories matching a search.'],
  ['github', 'GitHub releases', 'owner/repo, like vllm-project/vllm.'],
  ['web', 'Watched web page', 'Checked for changes; respects robots.txt.'],
];
const HELP: Record<string, string> = { 'robots': 'That site asks automated readers to stay away, so SmartWard won’t read it. Try its RSS feed instead.', 'took too long': 'The site is slow right now. Try again in a while.', 'redirect': 'The address moved somewhere SmartWard won’t follow. Open it in a browser, copy the new address, and edit the source.', '404': 'The feed moved or no longer exists. Look for its new feed address on the site.', 'rate limited': 'The site is limiting requests. SmartWard backs off automatically; it will retry later.', "private network": 'SmartWard only reads public websites.' };
const tryThis = (e: string) => Object.entries(HELP).find(([k]) => e.toLowerCase().includes(k))?.[1] || 'Check the address, then press Retry.';

export default function Sources({ onClose }: { onClose: () => void }) {
  const { data, reload } = useLoad<any[]>('/sources', undefined, 5000);
  const [adding, setAdding] = useState(false); const [busy, setBusy] = useState<number | null>(null);
  const retry = async (id: number) => { setBusy(id); try { await post(`/sources/${id}/refresh`); } catch {} setBusy(null); reload(); };
  return (
    <div className="h-full overflow-y-auto"><div className="mx-auto max-w-2xl p-5">
      <Title right={<><Btn onClick={() => setAdding(true)} kind="primary">+ Add source</Btn><Btn onClick={onClose}>Done</Btn></>}>Sources</Title>
      {(data || []).length === 0 && <Empty title="No sources yet">Follow blogs, arXiv, Hacker News, GitHub releases or a web page.</Empty>}
      <div className="space-y-2">{(data || []).map(s => (
        <Card key={s.id}><div className="flex items-start justify-between gap-3"><div className="min-w-0">
          <div className="flex items-center gap-2"><span className="truncate font-medium">{s.name}</span><Badge>{s.kind}</Badge>{!s.enabled && <Badge tone="amber">Paused</Badge>}</div>
          <div className="mt-0.5 truncate text-xs text-zinc-500">{s.url || s.query} · {s.n} articles · {s.last_fetched ? 'checked ' + ago(s.last_fetched) : 'not checked yet'}</div>
          {s.last_status === 'error' && <div className="mt-2 rounded-lg border border-red-900/60 bg-red-950/30 p-2 text-xs"><div className="text-red-300">{s.last_error}</div><div className="mt-1 text-zinc-400">What to try: {tryThis(s.last_error || '')}</div></div>}</div>
          <div className="flex shrink-0 gap-1">{s.last_status === 'error' && <Btn small onClick={() => retry(s.id)} disabled={busy === s.id}>{busy === s.id ? <Spin /> : 'Retry'}</Btn>}
            <Btn small onClick={async () => { await patch(`/sources/${s.id}`, { enabled: s.enabled ? 0 : 1 }); reload(); }}>{s.enabled ? 'Pause' : 'Resume'}</Btn>
            <Btn small kind="danger" onClick={async () => { if (await ask.confirm({ title: `Stop following “${s.name}”?`, body: 'Its articles are removed from Reading.', confirmLabel: 'Remove', danger: true })) { try { await del(`/sources/${s.id}`); toast.ok(`Removed “${s.name}”.`); } catch (e) { toast.error(errText(e)); } reload(); } }}>Remove</Btn></div></div></Card>))}</div>
      {adding && <AddSource onClose={() => { setAdding(false); reload(); }} />}
    </div></div>
  );
}

export function AddSource({ onClose, projectId }: { onClose: () => void; projectId?: number }) {
  const [kind, setKind] = useState('rss'); const [url, setUrl] = useState(''); const [query, setQuery] = useState(''); const [name, setName] = useState('');
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [shareUrl, setShareUrl] = useState('');
  const needsUrl = kind === 'rss' || kind === 'web'; const needsQuery = kind === 'arxiv' || kind === 'hn' || kind === 'github';
  const add = async () => { setBusy(true); setErr(''); try { await post('/sources', { kind, url: needsUrl ? url : undefined, query: needsQuery ? query : undefined, name: name || undefined, project_id: projectId }); onClose(); } catch (e) { setErr(errText(e)); } setBusy(false); };
  const share = async () => { setBusy(true); setErr(''); try { await post('/share', { url: shareUrl, project_id: projectId }); onClose(); } catch (e) { setErr(errText(e)); } setBusy(false); };
  const bm = `javascript:(()=>{fetch('${location.origin}/api/share',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({url:location.href})}).then(()=>alert('Added to SmartWard'))})()`;
  return (
    <Modal title="Add a source" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Type"><select className={inputCls} value={kind} onChange={e => setKind(e.target.value)}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <div className="text-xs text-zinc-500">{KINDS.find(k => k[0] === kind)?.[2]}</div>
        {needsUrl && <Field label="Link"><input className={inputCls} value={url} onChange={e => setUrl(e.target.value)} placeholder="https://…" autoFocus /></Field>}
        {needsQuery && <Field label={kind === 'github' ? 'Repository' : 'Search or category'}><input className={inputCls} value={query} onChange={e => setQuery(e.target.value)} autoFocus placeholder={kind === 'github' ? 'owner/repo' : kind === 'arxiv' ? 'cs.CL' : 'llm inference'} /></Field>}
        <Field label="Name (optional)"><input className={inputCls} value={name} onChange={e => setName(e.target.value)} /></Field>
        <Err>{err}</Err>
        <div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" onClick={add} disabled={busy || (needsUrl ? !url : needsQuery ? !query : false)}>{busy ? <><Spin /> Checking…</> : 'Add'}</Btn></div>
        <hr className="border-zinc-800" />
        <Field label="Or save a single page (Add to SmartWard)"><div className="flex gap-2"><input className={inputCls} value={shareUrl} onChange={e => setShareUrl(e.target.value)} placeholder="https://…" /><Btn onClick={share} disabled={busy || !shareUrl}>Save</Btn></div></Field>
        <div className="text-xs text-zinc-500">Tip: drag <a className="text-indigo-400 underline" href={bm} onClick={e => e.preventDefault()}>Add to SmartWard</a> to your bookmarks bar to save any page you’re reading, or <button type="button" className="text-indigo-400 underline" onClick={() => navigator.clipboard.writeText(bm).then(() => toast.ok('Bookmarklet copied. Paste it as the address of a new bookmark.'), () => toast.error('Couldn’t copy. Drag the link instead.'))}>copy it</button>. You can also drop a link onto this window.</div>
      </div>
    </Modal>
  );
}
