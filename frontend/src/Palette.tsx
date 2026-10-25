import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { get, post } from './api';
import { toast } from './feedback';
import { useNav } from './hooks';
import { setPref } from './theme';
import type { Tab } from './nav';

interface Item { key: string; label: string; hint: string; run: () => void }

/** Ctrl+K: jump anywhere, run a command, or search the library by name. */
export default function Palette({ lockOn }: { lockOn: boolean }) {
  const [open, setOpen] = useState(false); const [q, setQ] = useState(''); const [found, setFound] = useState<any>(null); const [sel, setSel] = useState(0);
  const { go, openArticle } = useNav(); const input = useRef<HTMLInputElement>(null); const id = useId(); const before = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); before.current = document.activeElement as HTMLElement; setQ(''); setFound(null); setSel(0); setOpen(o => !o); } };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, []);
  useEffect(() => { if (open) setTimeout(() => input.current?.focus(), 0); else before.current?.focus?.(); }, [open]);
  useEffect(() => {
    if (!open || !q.trim()) { setFound(null); return; }
    let live = true; const t = setTimeout(() => get('/search', { q }).then(r => live && setFound(r)).catch(() => {}), 120);
    return () => { live = false; clearTimeout(t); };
  }, [q, open]);

  const close = () => setOpen(false);
  const act = (fn: () => void) => () => { close(); fn(); };
  const post0 = (path: string, msg: string) => act(() => { post(path).then(() => toast.ok(msg)).catch(() => toast.error('That didn’t work.')); });
  const commands: Item[] = useMemo(() => {
    const nav = (label: string, tab: Tab): Item => ({ key: 'go-' + tab, label: 'Go to ' + label, hint: 'Go', run: act(() => go(tab)) });
    return [
      nav('Today', 'today'), nav('Reading', 'reading'), nav('Graph', 'graph'), nav('Chat', 'chat'), nav('Projects', 'projects'), nav('Settings', 'settings'),
      { key: 'sources', label: 'Go to Sources', hint: 'Go', run: act(() => go('reading', { sources: true, articleId: null })) },
      { key: 'refresh', label: 'Refresh sources now', hint: 'Do', run: post0('/refresh', 'Checking your sources…') },
      { key: 'index', label: 'Index new articles now', hint: 'Do', run: post0('/pipeline/run', 'Indexing…') },
      { key: 'link', label: 'Save a link…', hint: 'Do', run: act(() => window.dispatchEvent(new Event('sw-add-link'))) },
      ...(lockOn ? [{ key: 'lock', label: 'Lock SmartWard', hint: 'Do', run: act(() => window.dispatchEvent(new Event('sw-lock'))) }] : []),
      { key: 'light', label: 'Use the light theme', hint: 'Do', run: act(() => setPref('light')) },
      { key: 'dark', label: 'Use the dark theme', hint: 'Do', run: act(() => setPref('dark')) },
      { key: 'system', label: 'Match the system theme', hint: 'Do', run: act(() => setPref('system')) },
      { key: 'help', label: 'Show keyboard shortcuts', hint: 'Help', run: act(() => window.dispatchEvent(new Event('sw-help'))) },
    ];
  }, [lockOn]);
  const items: Item[] = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const cmds = needle ? commands.filter(c => c.label.toLowerCase().includes(needle)) : commands;
    const hits: Item[] = found ? [
      ...found.articles.map((a: any) => ({ key: 'a' + a.id, label: a.title, hint: 'Article', run: act(() => openArticle(a.id)) })),
      ...found.themes.map((t: any) => ({ key: 't' + t.id, label: t.name, hint: 'Theme · ' + t.type, run: act(() => go('graph', { themeId: t.id })) })),
      ...found.projects.map((p: any) => ({ key: 'p' + p.id, label: p.name, hint: 'Project', run: act(() => go('projects', { projectId: p.id })) })),
      ...found.conversations.map((c: any) => ({ key: 'c' + c.id, label: c.title, hint: 'Chat', run: act(() => go('chat', { convId: c.id })) })),
      ...found.sources.map((s: any) => ({ key: 's' + s.id, label: s.name, hint: 'Source', run: act(() => go('reading', { sources: true, articleId: null })) })),
    ] : [];
    return [...cmds, ...hits];
  }, [q, found, commands]);
  useEffect(() => { setSel(0); }, [q]);
  if (!open) return null;
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => Math.min(items.length - 1, s + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => Math.max(0, s - 1)); }
    else if (e.key === 'Enter') { e.preventDefault(); items[sel]?.run(); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[12vh]" onMouseDown={e => { if (e.target === e.currentTarget) close(); }}>
      <div role="dialog" aria-modal="true" aria-label="Command palette" className="w-full max-w-xl overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl" onKeyDown={onKey}>
        <input ref={input} value={q} onChange={e => setQ(e.target.value)} placeholder="Type a command, or search articles, themes, projects, chats…" role="combobox" aria-expanded aria-controls={id} aria-activedescendant={items[sel] ? `${id}-${sel}` : undefined} aria-label="Search or run a command"
          className="w-full border-b border-zinc-800 bg-transparent px-4 py-3 text-sm outline-none" />
        <ul id={id} role="listbox" className="max-h-[50vh] overflow-y-auto py-1">
          {items.length === 0 && <li className="px-4 py-3 text-sm text-zinc-500">Nothing matches.</li>}
          {items.map((it, i) => (
            <li key={it.key} id={`${id}-${i}`} role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onClick={it.run}
              ref={el => { if (i === sel) el?.scrollIntoView({ block: 'nearest' }); }}
              className={'flex cursor-pointer items-center justify-between gap-3 px-4 py-2 text-sm ' + (i === sel ? 'bg-indigo-600 text-white' : 'text-zinc-200')}>
              <span className="truncate">{it.label}</span><span className={'shrink-0 text-xs ' + (i === sel ? 'text-white/80' : 'text-zinc-500')}>{it.hint}</span></li>))}
        </ul>
      </div>
    </div>
  );
}
