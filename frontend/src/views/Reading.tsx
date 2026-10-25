import { useEffect, useState } from 'react';
import { get, patch, post, errText, ago } from '../api';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Empty, Err, Progress, Seg, cx } from '../ui';
import { toast } from '../feedback';
import Reader from './Reader';
import Sources from './Sources';

export function ArticleRow({ a, active, onOpen, onStar }: { a: any; active?: boolean; onOpen: () => void; onStar?: () => void }) {
  const pct = a.relevance != null ? Math.round(a.relevance * 100) : null;
  return (
    <div data-article-id={a.id} className={cx('flex items-start gap-2 overflow-hidden break-words border-b border-zinc-800/70 hover:bg-zinc-900 focus-within:bg-zinc-900', active && 'bg-zinc-900')}>
      <button type="button" onClick={onOpen} aria-current={active ? 'true' : undefined} aria-label={`${a.read ? '' : 'Unread. '}${a.starred ? 'Starred. ' : ''}${a.title}`}
        className="flex min-w-0 flex-1 items-start gap-2 px-4 py-3 text-left">
        {!a.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-400" aria-hidden />}
        <span className="min-w-0 flex-1">
          <span className={cx('block text-sm leading-snug', a.read ? 'text-zinc-400' : 'font-medium text-zinc-100')}>{a.title}</span>
          <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-zinc-500"><span className="truncate">{a.source}</span><span>{ago(a.published)}</span>{!a.relevant && <Badge>Off-topic</Badge>}{a.private && <Badge tone="amber">Private</Badge>}</span>
          {a.teaser && <span className="mt-1 line-clamp-2 block text-xs text-zinc-500">{a.teaser}</span>}
        </span>
      </button>
      <div className="flex shrink-0 flex-col items-end gap-1 py-3 pr-4">
        {onStar && <button type="button" onClick={onStar} aria-pressed={!!a.starred} aria-label={a.starred ? 'Unstar' : 'Star'} className={a.starred ? 'text-amber-400' : 'text-zinc-500 hover:text-zinc-300'}>{a.starred ? '★' : '☆'}</button>}
        {pct != null && <span className="text-[11px] text-zinc-500" title="How closely this matches your interests and projects">{pct}%</span>}
      </div>
    </div>
  );
}

export default function Reading() {
  const { articleId, openArticle, sources, go } = useNav();
  const [filter, setFilter] = useState('unread'); const [sort, setSort] = useState('newest'); const [q, setQ] = useState(''); const [qq, setQq] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { const t = setTimeout(() => setQq(q), 350); return () => clearTimeout(t); }, [q]);
  const { data, error, reload, setData } = useLoad<any>('/articles', { filter, sort, q: qq }, 5000);
  const { data: srcs, reload: reloadSrc } = useLoad<any[]>('/sources', undefined, 8000);
  const failing = (srcs || []).filter(s => s.last_status === 'error');
  const p = data?.pipeline;
  const pct = p?.total ? Math.round((p.done / p.total) * 100) : 0;

  const refresh = async () => { setBusy(true); try { await post('/refresh'); toast.info('Checking your sources…'); } catch (e) { toast.error(errText(e)); } setTimeout(() => { reload(); reloadSrc(); setBusy(false); }, 1500); };
  const flip = (id: number, starred: boolean) => setData((d: any) => d && { ...d, items: d.items.map((x: any) => x.id === id ? { ...x, starred } : x) });
  const star = async (a: any) => {
    flip(a.id, !a.starred);                                   // show it at once; undo the change if it didn't save
    try { await patch(`/articles/${a.id}`, { starred: !a.starred }); reload(); } catch (e) { flip(a.id, a.starred); toast.error(errText(e)); }
  };
  const markAllRead = async () => {
    const ids = (data?.items || []).filter((x: any) => !x.read).map((x: any) => x.id);
    if (!ids.length) return;
    try { await post('/articles/mark-read', { ids }); reload(); toast.ok(`Marked ${ids.length} as read.`, async () => { await post('/articles/mark-read', { ids, read: false }); reload(); }); }
    catch (e) { toast.error(errText(e)); }
  };

  if (sources) return <Sources onClose={() => go('reading', { sources: false })} />;
  const items: any[] = data?.items || [];
  const c = data?.counts;

  return (
    <div className="flex h-full">
      <section className={cx('flex min-h-0 w-full flex-col border-zinc-800 md:w-[26rem] md:shrink-0 md:border-r', articleId != null && 'hidden md:flex')}>
        <div className="space-y-2 border-b border-zinc-800 p-3">
          <div className="flex items-center justify-between"><h1 className="text-lg font-semibold">Reading</h1>
            <div className="flex gap-1.5"><Btn small onClick={() => go('reading', { sources: true })}>Sources{failing.length > 0 && <Badge tone="red">{failing.length}</Badge>}</Btn><Btn small onClick={refresh} disabled={busy || p?.running}>↻ Refresh</Btn></div></div>
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search keywords or meaning…" className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm outline-none focus:border-indigo-500" aria-label="Search" />
          {!qq && <div className="flex items-center justify-between gap-2">
            <Seg value={filter} onChange={setFilter} options={[['unread', `Unread${c ? ' ' + (c.unread || 0) : ''}`], ['starred', `Starred${c ? ' ' + (c.starred || 0) : ''}`], ['all', 'All']]} />
            <select value={sort} onChange={e => setSort(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs" aria-label="Sort"><option value="newest">Newest</option><option value="relevant">Most relevant</option></select></div>}
          {p?.running && <Progress value={pct} label={`${p.step}… ${p.total ? p.done + ' of ' + p.total : ''}`} />}
          {!p?.running && p?.waiting > 0 && <div className="text-xs text-zinc-500">{p.waiting} articles waiting to be indexed. <button className="text-indigo-400 hover:underline" onClick={() => post('/pipeline/run').then(reload)}>Index now</button></div>}
          {qq && data && <div className="text-xs text-zinc-500" role="status">{items.length === 0 ? 'No matches' : `${items.length} ${items.length === 1 ? 'match' : 'matches'}`}</div>}
          {!qq && filter === 'unread' && items.some((x: any) => !x.read) && <div className="flex justify-end"><Btn small kind="ghost" onClick={markAllRead}>Mark all read</Btn></div>}
        </div>
        {failing.length > 0 && (
          <button onClick={() => go('reading', { sources: true })} className="border-b border-red-900/50 bg-red-950/30 px-4 py-2 text-left text-xs text-red-300">
            {failing.length === 1 ? `“${failing[0].name}” couldn’t be refreshed.` : `${failing.length} sources couldn’t be refreshed.`} Click to see what to try.</button>)}
        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          {error && <div className="p-3"><Err>{error}</Err></div>}
          {items.map(a => <ArticleRow key={a.id} a={a} active={a.id === articleId} onOpen={() => openArticle(a.id)} onStar={() => star(a)} />)}
          {!error && items.length === 0 && data && (qq ? <Empty icon="⌕" title="Nothing found">Try other words — search covers every article, including off-topic ones.</Empty> :
            filter === 'unread' ? <Empty icon="✓" title="You're all caught up">{(srcs || []).length === 0 ? <>Add a source to start reading. <button className="text-indigo-400 underline" onClick={() => go('reading', { sources: true })}>Add one</button></> : 'Refresh to check for new articles.'}</Empty> :
              filter === 'starred' ? <Empty icon="☆" title="No starred articles">Star an article to keep it here.</Empty> : <Empty title="No articles yet">Add a source, then refresh.</Empty>)}
        </div>
      </section>
      <section className={cx('min-w-0 flex-1', articleId == null && 'hidden md:block')}>
        {articleId != null ? <Reader id={articleId} onBack={() => openArticle(null)} onChanged={reload} />
          : <div className="hidden h-full items-center justify-center md:flex"><Empty icon="▤" title="Pick an article">Each one opens with a five-question summary.</Empty></div>}
      </section>
    </div>
  );
}
