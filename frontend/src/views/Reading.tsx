import { useEffect, useState } from 'react';
import { get, patch, post, errText, ago } from '../api';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Empty, Err, Progress, Seg, cx } from '../ui';
import Reader from './Reader';
import Sources from './Sources';

export function ArticleRow({ a, active, onOpen, onStar }: { a: any; active?: boolean; onOpen: () => void; onStar?: () => void }) {
  const pct = a.relevance != null ? Math.round(a.relevance * 100) : null;
  return (
    <div role="button" tabIndex={0} onClick={onOpen} onKeyDown={e => e.key === 'Enter' && onOpen()}
      className={cx('cursor-pointer overflow-hidden break-words border-b border-zinc-800/70 px-4 py-3 hover:bg-zinc-900', active && 'bg-zinc-900')}
      aria-label={`${a.read ? '' : 'Unread. '}${a.starred ? 'Starred. ' : ''}${a.title}`}>
      <div className="flex items-start gap-2">
        {!a.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-400" aria-hidden />}
        <div className="min-w-0 flex-1">
          <div className={cx('text-sm leading-snug', a.read ? 'text-zinc-400' : 'font-medium text-zinc-100')}>{a.title}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-zinc-500"><span className="truncate">{a.source}</span><span>{ago(a.published)}</span>{!a.relevant && <Badge>Off-topic</Badge>}{a.private && <Badge tone="amber">Private</Badge>}</div>
          {a.teaser && <div className="mt-1 line-clamp-2 text-xs text-zinc-500">{a.teaser}</div>}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {onStar && <button onClick={e => { e.stopPropagation(); onStar(); }} aria-label={a.starred ? 'Unstar' : 'Star'} className={a.starred ? 'text-amber-400' : 'text-zinc-600 hover:text-zinc-300'}>{a.starred ? '★' : '☆'}</button>}
          {pct != null && <span className="text-[11px] text-zinc-500" title="How closely this matches your interests and projects">{pct}%</span>}
        </div>
      </div>
    </div>
  );
}

export default function Reading() {
  const { articleId, openArticle, sources, go } = useNav();
  const [filter, setFilter] = useState('unread'); const [sort, setSort] = useState('newest'); const [q, setQ] = useState(''); const [qq, setQq] = useState('');
  const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { const t = setTimeout(() => setQq(q), 350); return () => clearTimeout(t); }, [q]);
  const { data, error, reload } = useLoad<any>('/articles', { filter, sort, q: qq }, 5000);
  const { data: srcs, reload: reloadSrc } = useLoad<any[]>('/sources', undefined, 8000);
  const failing = (srcs || []).filter(s => s.last_status === 'error');
  const p = data?.pipeline;
  const pct = p?.total ? Math.round((p.done / p.total) * 100) : 0;

  const refresh = async () => { setBusy(true); setMsg(''); try { await post('/refresh'); setMsg('Refreshing sources…'); } catch (e) { setMsg(errText(e)); } setTimeout(() => { reload(); reloadSrc(); setBusy(false); }, 1500); };
  const star = async (a: any) => { await patch(`/articles/${a.id}`, { starred: !a.starred }); reload(); };

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
          {msg && <div className="text-xs text-zinc-400">{msg}</div>}
        </div>
        {failing.length > 0 && (
          <button onClick={() => go('reading', { sources: true })} className="border-b border-red-900/50 bg-red-950/30 px-4 py-2 text-left text-xs text-red-300">
            {failing.length === 1 ? `“${failing[0].name}” couldn’t be refreshed.` : `${failing.length} sources couldn’t be refreshed.`} Tap to see what to try.</button>)}
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
