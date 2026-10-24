import { useCallback, useEffect, useRef, useState } from 'react';
import { create } from 'zustand';
import { get } from './api';

export type Tab = 'today' | 'reading' | 'graph' | 'chat' | 'projects' | 'settings';

interface Nav {
  tab: Tab; articleId: number | null; projectId: number | null; convId: number | null; themeId: number | null; sources: boolean;
  go: (t: Tab, extra?: Partial<Nav>) => void;
  openArticle: (id: number | null) => void;
}
export const useNav = create<Nav>((set) => ({
  tab: 'today', articleId: null, projectId: null, convId: null, themeId: null, sources: false,
  go: (tab, extra = {}) => set({ tab, sources: false, ...extra }),
  openArticle: (id) => set({ tab: 'reading', articleId: id, sources: false }),
}));

/** Fetch + refetch helper. `deps` re-run; `every` polls (ms). */
export function useLoad<T = any>(url: string | null, params?: any, every?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const key = JSON.stringify([url, params]);
  const alive = useRef(true);
  const reload = useCallback(async () => {
    if (!url) return;
    try { setData(await get<T>(url, params)); setError(null); }
    catch (e: any) { setError(e?.response?.data?.detail || e?.message || 'Failed'); }
    finally { if (alive.current) setLoading(false); }
  }, [key]);
  useEffect(() => {
    alive.current = true; setLoading(true); reload();
    if (!every) return () => { alive.current = false; };
    const id = setInterval(reload, every);
    return () => { alive.current = false; clearInterval(id); };
  }, [reload, every]);
  return { data, error, loading, reload, setData };
}

/** Read aloud with the system voice (article text never leaves the device). */
export const speech = {
  supported: typeof window !== 'undefined' && 'speechSynthesis' in window,
  queue: [] as string[], idx: 0, on: false, paused: false, rate: 1, listeners: new Set<() => void>(),
  notify() { speech.listeners.forEach(f => f()); },
  speak(parts: string[], rate = 1, voice = '') {
    speech.stop(); if (!speech.supported) return;
    speech.queue = parts.filter(p => p.trim()); speech.idx = 0; speech.on = true; speech.paused = false; speech.rate = rate;
    const next = () => {
      if (!speech.on || speech.idx >= speech.queue.length) { speech.on = false; speech.notify(); return; }
      const u = new SpeechSynthesisUtterance(speech.queue[speech.idx]);
      u.rate = speech.rate; const v = speechSynthesis.getVoices().find(v => v.name === voice); if (v) u.voice = v;
      u.onend = () => { if (speech.on && !speech.paused) { speech.idx++; next(); } };
      speechSynthesis.speak(u); speech.notify();
    };
    next();
  },
  pause() { speechSynthesis.pause(); speech.paused = true; speech.notify(); },
  resume() { speechSynthesis.resume(); speech.paused = false; speech.notify(); },
  skip(d: number) { if (!speech.on) return; speechSynthesis.cancel(); speech.idx = Math.max(0, Math.min(speech.queue.length, speech.idx + d)); const q = speech.queue.slice(speech.idx); speech.speak(q, speech.rate); },
  stop() { speech.on = false; speech.paused = false; if (speech.supported) speechSynthesis.cancel(); speech.notify(); },
};
export function useSpeech() {
  const [, tick] = useState(0);
  useEffect(() => { const f = () => tick(x => x + 1); speech.listeners.add(f); return () => { speech.listeners.delete(f); }; }, []);
  return speech;
}
