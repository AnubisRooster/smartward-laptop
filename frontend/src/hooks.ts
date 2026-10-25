import { useCallback, useEffect, useRef, useState } from 'react';
import { create } from 'zustand';
import { get, http } from './api';
import { HOME, Place, Tab, hashFor, parseHash } from './nav';

export type { Tab } from './nav';

interface Nav extends Place {
  go: (t: Tab, extra?: Partial<Place>) => void;
  openArticle: (id: number | null) => void;
}
export const useNav = create<Nav>((set) => ({
  ...(parseHash(typeof location !== 'undefined' ? location.hash : '') || HOME),
  go: (tab, extra = {}) => set({ tab, sources: false, ...extra }),
  openArticle: (id) => set({ tab: 'reading', articleId: id, sources: false }),
}));

/** Keeps the address and the screen in step: Back, Forward and Reload land where you were. Call once. */
export function useHashSync() {
  useEffect(() => {
    const place = (s: Place): Place => ({ tab: s.tab, articleId: s.articleId, projectId: s.projectId, convId: s.convId, themeId: s.themeId, sources: s.sources });
    const fromAddress = () => { const p = parseHash(location.hash); if (p) useNav.setState(p); };
    const toAddress = () => { const h = hashFor(place(useNav.getState())); if (location.hash !== h) location.hash = h; };
    toAddress();
    window.addEventListener('hashchange', fromAddress);
    const unsubscribe = useNav.subscribe(toAddress);
    return () => { window.removeEventListener('hashchange', fromAddress); unsubscribe(); };
  }, []);
}

/** Fetch + refetch helper. `deps` re-run; `every` polls (ms). */
/** True when two payloads are the same JSON, so an unchanged poll doesn't re-render. */
export const sameData = (a: unknown, b: unknown) => a === b || JSON.stringify(a) === JSON.stringify(b);

/**
 * Loads `url`, optionally every `every` ms. Polling pauses while the window is hidden and catches up
 * when it comes back; an unchanged payload is ignored; an older response never overwrites a newer one;
 * data stays on screen while the same endpoint reloads (no spinner flash).
 */
export function useLoad<T = any>(url: string | null, params?: any, every?: number) {
  const [data, setDataState] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const key = JSON.stringify([url, params]);
  const seq = useRef(0); const lastUrl = useRef(url); const current = useRef<T | null>(null);
  const put = useCallback((u: T | null | ((d: T | null) => T | null)) => { const v = typeof u === 'function' ? (u as any)(current.current) : u; if (!sameData(current.current, v)) { current.current = v; setDataState(v); } }, []);
  const reload = useCallback(async () => {
    if (!url) return;
    const mine = ++seq.current;
    try { const r = await get<T>(url, params); if (mine === seq.current) { put(r); setError(null); } }
    catch (e: any) { if (mine === seq.current) setError(e?.response?.data?.detail || e?.message || 'Failed'); }
    finally { if (mine === seq.current) setLoading(false); }
  }, [key]);
  useEffect(() => {
    if (lastUrl.current !== url) { lastUrl.current = url; put(null); setLoading(true); }
    reload();
    if (!every) return () => { seq.current++; };
    const tick = () => { if (!document.hidden) reload(); };
    const id = setInterval(tick, every);
    document.addEventListener('visibilitychange', tick);
    return () => { seq.current++; clearInterval(id); document.removeEventListener('visibilitychange', tick); };
  }, [reload, every]);
  return { data, error, loading, reload, setData: put };
}

/** What the speaker settings add up to right now. */
export interface SpeechConfig { engine: 'kokoro' | 'browser'; voice: string; rate: number; notice: string }

/** Splits long text at sentence ends so a natural voice can start quickly and skipping stays useful. */
export function chunkForSpeech(text: string, max = 380): string[] {
  const out: string[] = [];
  for (const para of text.split(/\n{2,}/)) {
    const sentences = para.replace(/\s+/g, ' ').trim().match(/[^.!?…]+[.!?…]+["')\]]*\s*|[^.!?…]+$/g) || [];
    let cur = '';
    for (const s of sentences) {
      if (cur && (cur + s).length > max) { out.push(cur.trim()); cur = ''; }
      cur += s;
      while (cur.length > max * 1.6) { const cut = cur.lastIndexOf(' ', max); const at = cut > 40 ? cut : max; out.push(cur.slice(0, at).trim()); cur = cur.slice(at); }
    }
    if (cur.trim()) out.push(cur.trim());
  }
  return out;
}

/** Read aloud, on this computer only: a natural voice from the local speech server when it's running,
 *  otherwise the browser's own voice. Article text never leaves this machine. */
export const speech = {
  supported: typeof window !== 'undefined',
  browserVoices: typeof window !== 'undefined' && 'speechSynthesis' in window,
  queue: [] as string[], idx: 0, on: false, paused: false, rate: 1, engine: '' as '' | 'kokoro' | 'browser', notice: '',
  listeners: new Set<() => void>(),
  token: 0, flat: [] as { part: number; text: string }[], cursor: 0,
  audio: null as HTMLAudioElement | null, clips: new Map<number, Promise<string>>(), aborts: new Set<AbortController>(), cfg: null as SpeechConfig | null,
  notify() { speech.listeners.forEach(f => f()); },

  /** Settings + whether the natural voice is up decide which voice speaks. */
  async resolve(rateHint: number, voiceHint: string): Promise<SpeechConfig> {
    const [s, t] = await Promise.all([get('/settings'), get('/tts/status').catch(() => ({ up: false }))]);
    const profile = s.tts_profile ? s.tts_profiles?.[s.tts_profile] : null;
    const rate = Number(profile?.rate ?? s.voice_rate ?? rateHint) || 1;
    const wantsNatural = s.tts_engine === 'kokoro' || (s.tts_engine !== 'browser' && t.up);
    if (wantsNatural && t.up) return { engine: 'kokoro', voice: profile?.voice || s.tts_voice || 'af_heart', rate, notice: '' };
    return { engine: 'browser', voice: voiceHint || s.voice_name || '', rate,
      notice: wantsNatural ? 'The natural voice isn’t running, so the browser voice is reading. Start SmartWard from its menu icon to bring it back.' : '' };
  },

  async speak(parts: string[], rate = 1, voice = '') {
    speech.stop();
    const queue = parts.filter(p => p.trim());
    if (!queue.length) return;
    const token = ++speech.token;
    speech.queue = queue; speech.idx = 0; speech.on = true; speech.paused = false; speech.notice = ''; speech.notify();
    let cfg: SpeechConfig;
    try { cfg = await speech.resolve(rate, voice); } catch { cfg = { engine: 'browser', voice, rate, notice: '' }; }
    if (token !== speech.token) return;
    speech.cfg = cfg; speech.engine = cfg.engine; speech.rate = cfg.rate; speech.notice = cfg.notice;
    if (cfg.engine === 'kokoro') {
      speech.flat = queue.flatMap((text, part) => chunkForSpeech(text).map(t => ({ part, text: t })));
      speech.cursor = 0; speech.clips.clear();
      void speech.runNatural(token);
    } else if (speech.browserVoices) speech.runBrowser(token);
    else { speech.on = false; speech.notice = 'This window can’t speak, and the natural voice isn’t running.'; }
    speech.notify();
  },

  clip(i: number): Promise<string> {
    const cached = speech.clips.get(i); if (cached) return cached;
    const c = speech.cfg!; const ctl = new AbortController(); speech.aborts.add(ctl);
    const p = http.post('/tts', { text: speech.flat[i].text, voice: c.voice, speed: c.rate }, { responseType: 'blob', signal: ctl.signal })
      .then(r => URL.createObjectURL(r.data as Blob)).finally(() => speech.aborts.delete(ctl));
    p.catch(() => {}); speech.clips.set(i, p); return p;
  },

  async runNatural(token: number) {
    const alive = () => token === speech.token && speech.on;
    while (alive() && speech.cursor < speech.flat.length) {
      const i = speech.cursor;
      speech.idx = speech.flat[i].part; speech.notify();
      if (i + 1 < speech.flat.length) speech.clip(i + 1);   // fetch the next piece while this one plays
      let url: string;
      try { url = await speech.clip(i); }
      catch (e: any) {
        if (!alive()) return;
        // The natural voice failed: finish with the browser voice from this part on.
        speech.notice = 'The natural voice stopped responding, so the browser voice is reading.';
        speech.engine = 'browser'; speech.queue = speech.queue.slice(speech.idx); speech.idx = 0;
        if (speech.browserVoices) speech.runBrowser(token); else { speech.on = false; }
        speech.notify(); return;
      }
      if (!alive()) return;
      await new Promise<void>(resolve => {
        const audio = new Audio(url); speech.audio = audio;
        audio.onended = () => resolve(); audio.onerror = () => resolve();
        void audio.play().catch(() => resolve());
      });
      if (!alive()) return;
      URL.revokeObjectURL(url); speech.clips.delete(i);
      speech.cursor++;
    }
    if (alive()) { speech.on = false; speech.audio = null; speech.notify(); }
  },

  runBrowser(token: number) {
    const next = () => {
      if (token !== speech.token || !speech.on || speech.idx >= speech.queue.length) { if (token === speech.token) { speech.on = false; speech.notify(); } return; }
      const u = new SpeechSynthesisUtterance(speech.queue[speech.idx]);
      u.rate = speech.rate; const v = speechSynthesis.getVoices().find(v => v.name === speech.cfg?.voice); if (v) u.voice = v;
      u.onend = () => { if (token === speech.token && speech.on && !speech.paused) { speech.idx++; next(); } };
      speechSynthesis.speak(u); speech.notify();
    };
    next();
  },

  pause() { if (speech.engine === 'kokoro') speech.audio?.pause(); else if (speech.browserVoices) speechSynthesis.pause(); speech.paused = true; speech.notify(); },
  resume() { if (speech.engine === 'kokoro') void speech.audio?.play(); else if (speech.browserVoices) speechSynthesis.resume(); speech.paused = false; speech.notify(); },
  skip(d: number) {
    if (!speech.on) return;
    const target = Math.max(0, Math.min(speech.queue.length, speech.idx + d));
    if (speech.engine === 'kokoro') {
      const at = speech.flat.findIndex(f => f.part >= target);
      const token = ++speech.token;               // ends the current run, then start a new one at the part
      speech.audio?.pause(); speech.audio = null; speech.aborts.forEach(c => c.abort()); speech.aborts.clear();
      speech.clips.forEach(p => p.then(u => URL.revokeObjectURL(u)).catch(() => {})); speech.clips.clear();
      speech.paused = false;
      if (at < 0) { speech.on = false; speech.notify(); return; }
      speech.cursor = at; void speech.runNatural(token);
    } else {
      speechSynthesis.cancel(); speech.idx = target; const token = ++speech.token; speech.paused = false;
      if (target >= speech.queue.length) { speech.on = false; speech.notify(); return; }
      speech.runBrowser(token);
    }
  },
  stop() {
    speech.token++; speech.on = false; speech.paused = false;
    speech.audio?.pause(); speech.audio = null; speech.aborts.forEach(c => c.abort()); speech.aborts.clear();
    speech.clips.forEach(p => p.then(u => URL.revokeObjectURL(u)).catch(() => {})); speech.clips.clear();
    if (speech.browserVoices) speechSynthesis.cancel();
    speech.notify();
  },

  /** Plays one sentence in a chosen voice and speed, for the Listen buttons in Settings. */
  async sample(engine: 'kokoro' | 'browser', voice: string, rate: number): Promise<string> {
    speech.stop();
    const text = 'This is how SmartWard will read your articles.';
    if (engine === 'kokoro') {
      const r = await http.post('/tts', { text, voice, speed: rate }, { responseType: 'blob' });
      const url = URL.createObjectURL(r.data as Blob); const audio = new Audio(url); speech.audio = audio;
      audio.onended = () => URL.revokeObjectURL(url); await audio.play(); return '';
    }
    if (!speech.browserVoices) return 'This window can’t speak with a browser voice.';
    const u = new SpeechSynthesisUtterance(text); u.rate = rate; const v = speechSynthesis.getVoices().find(v => v.name === voice); if (v) u.voice = v;
    speechSynthesis.speak(u); return '';
  },
};
export function useSpeech() {
  const [, tick] = useState(0);
  useEffect(() => { const f = () => tick(x => x + 1); speech.listeners.add(f); return () => { speech.listeners.delete(f); }; }, []);
  return speech;
}
