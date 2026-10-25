import { useEffect, useRef, useState } from 'react';
import { get, post } from './api';
import { Tab, useLoad, useNav, speech } from './hooks';
import { Progress, cx } from './ui';
import Today from './views/Today';
import Reading from './views/Reading';
import GraphView from './views/Graph';
import Chat from './views/Chat';
import Projects from './views/Projects';
import Settings from './views/Settings';
import Onboarding from './views/Onboarding';
import { onDesktopEvent } from './desktop';

const TABS: [Tab, string, string][] = [['today', 'Today', '☀'], ['reading', 'Reading', '▤'], ['graph', 'Graph', '⁂'], ['chat', 'Chat', '✎'], ['projects', 'Projects', '▣']];

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
  const { tab, go } = useNav();
  const { data: st, error, reload } = useLoad<any>('/status', undefined, 4000);
  const [locked, setLocked] = useState(() => { try { return sessionStorage.getItem('sw.unlocked') !== '1'; } catch { return true; } });
  const idle = useRef<any>(null);
  const lockOn = !!st?.lock_enabled;

  // The tray's "Lock now".
  useEffect(() => {
    let off = () => {};
    onDesktopEvent('lock-now', () => { if (lockOn) { speech.stop(); setLocked(true); try { sessionStorage.removeItem('sw.unlocked'); } catch {} } }).then(f => { off = f; });
    return () => off();
  }, [lockOn]);

  // Lock on launch and after the grace period away / idle; cover the app while hidden.
  useEffect(() => {
    if (!lockOn) return;
    let hiddenAt = 0;
    const lockAfter = async () => { const s = await get('/settings'); return (s.lock_after ?? 60) * 1000; };
    const onVis = async () => {
      if (document.hidden) hiddenAt = Date.now();
      else if (hiddenAt && Date.now() - hiddenAt > await lockAfter()) { speech.stop(); setLocked(true); try { sessionStorage.removeItem('sw.unlocked'); } catch {} }
    };
    const reset = () => { clearTimeout(idle.current); lockAfter().then(ms => { idle.current = setTimeout(() => { speech.stop(); setLocked(true); try { sessionStorage.removeItem('sw.unlocked'); } catch {} }, Math.max(ms, 60000) * 5); }); };
    document.addEventListener('visibilitychange', onVis); window.addEventListener('pointerdown', reset); window.addEventListener('keydown', reset); reset();
    return () => { document.removeEventListener('visibilitychange', onVis); window.removeEventListener('pointerdown', reset); window.removeEventListener('keydown', reset); clearTimeout(idle.current); };
  }, [lockOn]);

  if (!st) {
    return <div className="flex h-full items-center justify-center p-8 text-center">
      <div><div className="mb-2 text-lg">{error ? 'SmartWard’s backend isn’t running' : 'Starting…'}</div>
        {error && <div className="text-sm text-zinc-500">Start it from the SmartWard menu icon or run <code className="rounded bg-zinc-800 px-1">~/SmartWardApp/bin/start_smartward.sh</code></div>}</div></div>;
  }
  if (lockOn && locked) return <LockScreen onUnlock={() => { try { sessionStorage.setItem('sw.unlocked', '1'); } catch {} setLocked(false); }} />;
  if (!st.onboarding_completed) return <Onboarding status={st} onDone={reload} />;

  const p = st.pipeline;
  const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
  const Body = { today: Today, reading: Reading, graph: GraphView, chat: Chat, projects: Projects, settings: Settings }[tab];

  return (
    <div className="flex h-full flex-col md:flex-row">
      <nav className="flex shrink-0 gap-0.5 border-b border-zinc-800 bg-zinc-950 p-1.5 md:w-48 md:flex-col md:gap-1 md:border-b-0 md:border-r md:p-3" aria-label="Main">
        <div className="hidden px-2 pb-3 pt-1 md:block"><div className="text-lg font-semibold">SmartWard</div><div className="text-xs text-zinc-500">Local research strategist</div></div>
        {TABS.map(([id, label, icon]) => (
          <button key={id} onClick={() => go(id)} aria-current={tab === id ? 'page' : undefined}
            className={cx('flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[11px] md:flex-none md:flex-row md:gap-2 md:px-3 md:py-2 md:text-sm', tab === id ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200')}>
            <span className="w-4 text-center">{icon}</span><span>{label}</span></button>))}
        <div className="hidden flex-1 md:block" />
        <button onClick={() => go('settings')} className={cx('flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[11px] md:flex-none md:flex-row md:gap-2 md:px-3 md:py-2 md:text-sm', tab === 'settings' ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-900')}><span className="w-4 text-center">⚙</span><span>Settings</span></button>
        {lockOn && <button onClick={() => { speech.stop(); setLocked(true); try { sessionStorage.removeItem('sw.unlocked'); } catch {} }} className="hidden items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-900 md:flex"><span className="w-4 text-center">🔒</span>Lock now</button>}
      </nav>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        {p.running && (
          <div className="border-b border-zinc-800 bg-zinc-900/60 px-4 py-2"><Progress value={pct} label={`${p.step || 'Working'}… ${p.total ? `${p.done} of ${p.total}` : ''}`} /></div>)}
        <div className="min-h-0 flex-1 overflow-hidden"><Body /></div>
      </main>
    </div>
  );
}
