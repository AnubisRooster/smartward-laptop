import { useCallback, useEffect, useRef, useState } from 'react';
import { errText, get, post } from './api';
import { speech, useSpeech } from './hooks';
import { toast } from './feedback';
import { parseVoice, plainForSpeech } from './voiceInput';
import { takeAudioChat } from './voiceIntent';

export type HandsFreeStatus = 'off' | 'loading' | 'listening' | 'hearing' | 'thinking' | 'speaking';

interface Args {
  running: boolean;                 // the strategist is answering
  messages: any[];
  pending: any[];                   // approvals waiting for a yes or no
  send: (text: string) => Promise<void>;
  stop: () => Promise<void>;        // cancel the answer in progress
  decide: (approvalId: string, approved: boolean) => Promise<void>;
}

/**
 * Hands-free chat: listens (on this computer, through the speech server), sends each sentence when you pause,
 * reads the answer aloud, then listens again. It never listens while it speaks, and it switches itself off when
 * the window is hidden or the chat is left. The microphone is open only while this is on.
 */
export function useHandsFree(a: Args) {
  const [on, setOn] = useState(false); const [server, setServer] = useState<string>('off'); const [error, setError] = useState('');
  const sp = useSpeech();
  const cursor = useRef(0); const voiceTurn = useRef(false); const wasRunning = useRef(false); const announced = useRef(new Set<string>()); const latest = useRef(a); latest.current = a;
  const wasSpeaking = useRef(false);

  useEffect(() => { if (takeAudioChat()) setOn(true); }, []);

  const turnOff = useCallback(() => { setOn(false); speech.stop(); }, []);

  // The microphone follows `on`.
  useEffect(() => {
    if (!on) { post('/voice/stop').catch(() => {}); setServer('off'); return; }
    let alive = true; setError(''); setServer('loading');
    (async () => {
      try { await post('/voice/start'); const first = await get('/voice/poll', { after: 0 }); cursor.current = first.seq; }
      catch (e) { if (alive) { setError(errText(e)); setOn(false); } return; }
    })();
    const timer = setInterval(async () => {
      try {
        const r = await get('/voice/poll', { after: cursor.current });
        if (!alive) return;
        cursor.current = r.seq; setServer(r.ready ? r.state : 'loading');
        if (r.error) { setError(r.error); setOn(false); return; }
        for (const e of r.events) if (e.type === 'text') handle(e.text);
      } catch { /* the next poll will try again */ }
    }, 400);
    const hide = () => { if (document.hidden) turnOff(); };
    document.addEventListener('visibilitychange', hide); window.addEventListener('sw-lock', turnOff);
    return () => { alive = false; clearInterval(timer); document.removeEventListener('visibilitychange', hide); window.removeEventListener('sw-lock', turnOff); post('/voice/stop').catch(() => {}); };
  }, [on]);

  function handle(said: string) {
    const { running, pending, send, stop, decide } = latest.current;
    const cmd = parseVoice(said, { pending: pending.length > 0 });
    if (cmd.kind === 'stop-listening') { toast.info('Hands-free is off.'); turnOff(); }
    else if (cmd.kind === 'stop') { speech.stop(); if (running) stop(); }
    else if (cmd.kind === 'approve' || cmd.kind === 'decline') decide(pending[0].id, cmd.kind === 'approve');
    else if (running || pending.length) toast.info(`Heard “${cmd.text}”, but I’m still busy. Say “stop” to interrupt.`);
    else { voiceTurn.current = true; send(cmd.text); }
  }

  // Never listen to our own voice: pause while reading, resume a moment after.
  useEffect(() => {
    if (!on) { wasSpeaking.current = false; return; }
    if (sp.on && !wasSpeaking.current) post('/voice/pause').catch(() => {});
    if (!sp.on && wasSpeaking.current) post('/voice/resume').catch(() => {});
    wasSpeaking.current = sp.on;
  }, [sp.on, on]);

  // Read the answer to a spoken question.
  useEffect(() => {
    if (wasRunning.current && !a.running && voiceTurn.current && on) {
      voiceTurn.current = false;
      const last = [...a.messages].reverse().find(m => m.role === 'assistant');
      if (last?.content && !last.meta?.cancelled) speech.speak(plainForSpeech(last.content));
    }
    wasRunning.current = a.running;
  }, [a.running, on]);

  // A tool is waiting for you: say so, and say how to answer.
  useEffect(() => {
    if (!on) return;
    const next = a.pending.find(p => !announced.current.has(p.id));
    if (next) { announced.current.add(next.id); speech.speak([`Approval needed. ${next.title}. ${String(next.detail).slice(0, 200)}. Say approve or decline.`]); }
  }, [a.pending.length, on]);

  const status: HandsFreeStatus = !on ? 'off' : sp.on ? 'speaking' : a.running ? 'thinking' : server === 'loading' ? 'loading' : server === 'hearing' ? 'hearing' : 'listening';
  return { on, status, error, toggle: () => (on ? turnOff() : (setError(''), setOn(true))), turnOff };
}
