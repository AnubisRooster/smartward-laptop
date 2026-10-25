import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { get, post } from './api';
import { Tab, useHashSync, useLoad, useNav, speech } from './hooks';
import { Progress, Spin, cx } from './ui';
import { FeedbackHost } from './feedback';
import Shortcuts from './Shortcuts';
import Palette from './Palette';
import Links from './Links';
import { onPhone } from './device';
import RemoteSignIn, { PhoneAccount } from './RemoteSignIn';
import { Sun, Newspaper, Share2, MessageSquare, FolderKanban, Settings as SettingsIcon, Lock, Rss, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import Today from './views/Today';
import Reading from './views/Reading';
const GraphView = lazy(() => import('./views/Graph'));
const Chat = lazy(() => import('./views/Chat'));
const Projects = lazy(() => import('./views/Projects'));
const Settings = lazy(() => import('./views/Settings'));
import Onboarding from './views/Onboarding';
import { onDesktopEvent } from './desktop';

const TABS: [Tab, string, typeof Sun][] = [['today', 'Today', Sun], ['reading', 'Reading', Newspaper], ['graph', 'Graph', Share2], ['chat', 'Chat', MessageSquare], ['projects', 'Projects', FolderKanban]];

function LockScreen({ onUnlock }: { onUnlock: () => void }) {
  const [pin, setPin] = useState(''); const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true); setErr('');
    try { const r = await post('/lock/verify', { pin }); if (r.ok) onUnlock(); else { setErr('Wrong PIN.'); setPin(''); } } catch { setErr('Can’t reach the backend.'); }
    setBusy(false);
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950">
      <form onSubmit={e => { e.preventDefault(); submit(); }} className="w-72 text-center">
        <div className="mb-2 text-4xl">🔒</div><div className="mb-4 text-lg font-semibold">SmartWard is locked</div>
        <input autoFocus type="password" inputMode="numeric" value={pin} onChange={e => setPin(e.target.value)} placeholder="PIN"
          className="mb-3 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-center text-lg tracking-widest outline-none focus:border-indigo-500" />
        {err && <div className="mb-2 text-sm text-red-400">{err}</div>}
        <button disabled={busy || !pin} className="w-full rounded-lg bg-indigo-600 py-2 font-medium disabled:opacity-40">Unlock</button>
      </form>
    </div>
  );
}

export default function App() {
  useHashSync();
  const { tab, go, sources } = useNav();
  const { data: st, error, reload } = useLoad<any>('/status', undefined, 4000);
  const [locked, setLocked] = useState(() => { try { return sessionStorage.getItem('sw.unlocked') !== '1'; } catch { return true; } });
  const [rail, setRail] = useState(() => { try { return localStorage.getItem('sw.rail') === '1'; } catch { return false; } });
  const [needSignIn, setNeedSignIn] = useState(false);
  useEffect(() => { const f = () => setNeedSignIn(true); window.addEventListener('sw-remote-auth', f); return () => window.removeEventListener('sw-remote-auth', f); }, []);
  const idle = useRef<any>(null);
  const firstBuild = useRef<number | null>(null);
  useEffect(() => { if (st?.ui_build == null) return; if (firstBuild.current == null) firstBuild.current = st.ui_build; }, [st?.ui_build]);
  const stale = st?.ui_build != null && firstBuild.current != null && st.ui_build !== firstBuild.current;
  const lockOn = !!st?.lock_enabled;
  const lockNow = () => { speech.stop(); setLocked(true); try { sessionStorage.removeItem('sw.unlocked'); } catch {} };
  useEffect(() => { const f = () => lockNow(); window.addEventListener('sw-lock', f); return () => window.removeEventListener('sw-lock', f); }, []);
  const toggleRail = () => setRail(r => { try { localStorage.setItem('sw.rail', r ? '0' : '1'); } catch {} return !r; });

  // The tab title shows what's unread, so you can tell from the window list.
  useEffect(() => { document.title = st?.unread > 0 ? `(${st.unread}) SmartWard` : 'SmartWard'; }, [st?.unread]);

  // The tray's "Lock now".
  useEffect(() => {
    let off = () => {};
    onDesktopEvent('lock-now', () => { if (lockOn) lockNow(); }).then(f => { off = f; });
    return () => off();
  }, [lockOn]);

  // Lock on launch and after the grace period away / idle; cover the app while hidden.
  useEffect(() => {
    if (!lockOn) return;
    let hiddenAt = 0;
    const lockAfter = async () => { const s = await get('/settings'); return (s.lock_after ?? 60) * 1000; };
    const onVis = async () => {
      if (document.hidden) hiddenAt = Date.now();
      else if (hiddenAt && Date.now() - hiddenAt > await lockAfter()) lockNow();
    };
    const reset = () => { clearTimeout(idle.current); lockAfter().then(ms => { idle.current = setTimeout(lockNow, Math.max(ms, 60000) * 5); }); };
    document.addEventListener('visibilitychange', onVis); window.addEventListener('pointerdown', reset); window.addEventListener('keydown', reset); reset();
    return () => { document.removeEventListener('visibilitychange', onVis); window.removeEventListener('pointerdown', reset); window.removeEventListener('keydown', reset); clearTimeout(idle.current); };
  }, [lockOn]);

  if (needSignIn) return <RemoteSignIn onDone={() => { setNeedSignIn(false); reload(); }} />;
  if (!st) {
    return <><div className="flex h-full items-center justify-center p-8 text-center" role={error ? 'alert' : 'status'}>
      <div><div className="mb-2 text-lg">{error ? (onPhone ? 'Can’t reach your laptop' : 'SmartWard’s backend isn’t running') : 'Starting…'}</div>
        {error && <>
          <div className="mb-3 text-sm text-zinc-500">{onPhone ? <>Your laptop may be asleep, offline, or SmartWard may not be running. Check that it’s on and that Tailscale is connected on both devices, then try again.</> : <>SmartWard normally restarts it by itself. If this stays, quit SmartWard from the tray icon and open it again.<br />The log is in <code className="rounded bg-zinc-800 px-1">~/.local/state/smartward/api.log</code>.</>}</div>
          <button onClick={() => reload()} className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm hover:bg-zinc-700">Try again</button></>}</div></div><FeedbackHost /></>;
  }
  if (lockOn && locked) return <><LockScreen onUnlock={() => { try { sessionStorage.setItem('sw.unlocked', '1'); } catch {} setLocked(false); }} /><FeedbackHost /></>;
  if (!st.onboarding_completed) return <><Onboarding status={st} onDone={reload} /><FeedbackHost /></>;

  const p = st.pipeline;
  const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
  const Body = { today: Today, reading: Reading, graph: GraphView, chat: Chat, projects: Projects, settings: onPhone ? PhoneAccount : Settings }[tab];
  const navBtn = (active: boolean, label: string, Icon: typeof Sun, onClick: () => void, extra?: string) => (
    <button key={label} onClick={onClick} aria-current={active ? 'page' : undefined} title={rail ? label : undefined} aria-label={rail ? label : undefined}
      className={cx('flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[11px] md:flex-none md:flex-row md:gap-2 md:px-3 md:py-2 md:text-sm', rail && 'md:justify-center md:px-0', active ? 'bg-zinc-800 text-zinc-50' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200', extra)}>
      <Icon size={16} aria-hidden className="shrink-0" /><span className={cx(rail && 'md:hidden')}>{label}</span></button>);

  return (
    <div className="flex h-full flex-col md:flex-row">
      <nav className={cx('order-2 flex shrink-0 gap-0.5 border-t border-zinc-800 bg-zinc-950 p-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))] md:order-none md:flex-col md:gap-1 md:border-t-0 md:border-r md:p-3', rail ? 'md:w-16 md:px-2' : 'md:w-48')} aria-label="Main">
        <div className={cx('hidden px-2 pb-3 pt-1 md:block', rail && 'md:hidden')}><div className="text-lg font-semibold">SmartWard</div><div className="text-xs text-zinc-500">Local research strategist</div></div>
        {TABS.map(([id, label, Icon]) => navBtn(tab === id && !(id === 'reading' && sources), label, Icon, () => go(id)))}
        {navBtn(tab === 'reading' && sources, 'Sources', Rss, () => go('reading', { sources: true, articleId: null }))}
        <div className="hidden flex-1 md:block" />
        {navBtn(tab === 'settings', 'Settings', SettingsIcon, () => go('settings'))}
        {lockOn && <button onClick={lockNow} title="Lock SmartWard" aria-label="Lock SmartWard" className={cx('hidden items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-900 md:flex', rail && 'md:justify-center md:px-0')}><Lock size={16} aria-hidden /><span className={cx(rail && 'md:hidden')}>Lock</span></button>}
        <button onClick={toggleRail} title={rail ? 'Expand sidebar' : 'Collapse sidebar'} aria-label={rail ? 'Expand sidebar' : 'Collapse sidebar'} className={cx('hidden items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-900 hover:text-zinc-300 md:flex', rail && 'md:justify-center md:px-0')}>{rail ? <PanelLeftOpen size={16} aria-hidden /> : <PanelLeftClose size={16} aria-hidden />}<span className={cx(rail && 'md:hidden')}>Collapse</span></button>
      </nav>
      <main className="order-1 flex min-h-0 min-w-0 flex-1 flex-col md:order-none">
        {p.running && tab !== 'reading' && (
          <div className="border-b border-zinc-800 bg-zinc-900/60 px-4 py-2"><Progress value={pct} label={`${p.step || 'Working'}… ${p.total ? `${p.done} of ${p.total}` : ''}`} /></div>)}
        {stale && <div role="status" className="flex items-center justify-between gap-3 border-b border-indigo-800 bg-indigo-950/40 px-4 py-2 text-sm">SmartWard was updated. <button className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-500" onClick={() => location.reload()}>Reload to use the new version</button></div>}
        <div className="min-h-0 flex-1 overflow-hidden"><Suspense fallback={<div className="p-6" role="status"><Spin /></div>}><Body /></Suspense></div>
      </main>
      <Shortcuts />
      <Palette lockOn={lockOn} />
      <Links />
      <FeedbackHost />
    </div>
  );
}
