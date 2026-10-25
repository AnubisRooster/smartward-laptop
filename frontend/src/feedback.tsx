import { useEffect, useState } from 'react';
import { create } from 'zustand';
import { Btn, Modal, inputCls } from './ui';

// ---- Toasts: short messages that go away, optionally with Undo ----
interface ToastItem { id: number; text: string; kind: 'ok' | 'error' | 'info'; undo?: () => void }
let nextId = 1;
const useToasts = create<{ items: ToastItem[]; push: (t: Omit<ToastItem, 'id'>) => number; dismiss: (id: number) => void }>((set) => ({
  items: [],
  push: (t) => { const id = nextId++; set(s => ({ items: [...s.items.slice(-3), { ...t, id }] })); return id; },
  dismiss: (id) => set(s => ({ items: s.items.filter(i => i.id !== id) })),
}));
const show = (kind: ToastItem['kind'], text: string, undo?: () => void) => useToasts.getState().push({ kind, text, undo });
export const toast = {
  ok: (text: string, undo?: () => void) => show('ok', text, undo),
  info: (text: string) => show('info', text),
  error: (text: string) => show('error', text),
};

function Toaster() {
  const { items, dismiss } = useToasts();
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" role="region" aria-label="Notifications">
      {items.map(t => <ToastView key={t.id} t={t} onDone={() => dismiss(t.id)} />)}
    </div>
  );
}
function ToastView({ t, onDone }: { t: ToastItem; onDone: () => void }) {
  useEffect(() => { const ms = t.kind === 'error' ? 9000 : t.undo ? 7000 : 3500; const h = setTimeout(onDone, ms); return () => clearTimeout(h); }, []);
  const tone = { ok: 'border-emerald-800 bg-emerald-950/90 text-emerald-100', error: 'border-red-800 bg-red-950/90 text-red-100', info: 'border-zinc-700 bg-zinc-900/95 text-zinc-100' }[t.kind];
  return (
    <div role={t.kind === 'error' ? 'alert' : 'status'} className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3 py-2 text-sm shadow-lg ${tone}`}>
      <span className="min-w-0 flex-1 break-words">{t.text}</span>
      {t.undo && <button className="shrink-0 font-medium underline" onClick={() => { t.undo?.(); onDone(); }}>Undo</button>}
      <button className="shrink-0 opacity-60 hover:opacity-100" onClick={onDone} aria-label="Dismiss">✕</button>
    </div>
  );
}

// ---- Dialogs: in-app replacements for confirm() and prompt() ----
type Req =
  | { kind: 'confirm'; title: string; body?: string; confirmLabel: string; danger: boolean; resolve: (ok: boolean) => void }
  | { kind: 'prompt'; title: string; body?: string; initial: string; label: string; confirmLabel: string; resolve: (v: string | null) => void };
const useDialog = create<{ req: Req | null; set: (r: Req | null) => void }>((set) => ({ req: null, set: (req) => set({ req }) }));

export const ask = {
  confirm: (o: { title: string; body?: string; confirmLabel?: string; danger?: boolean }) =>
    new Promise<boolean>(resolve => useDialog.getState().set({ kind: 'confirm', title: o.title, body: o.body, confirmLabel: o.confirmLabel || 'OK', danger: !!o.danger, resolve })),
  prompt: (o: { title: string; body?: string; initial?: string; label?: string; confirmLabel?: string }) =>
    new Promise<string | null>(resolve => useDialog.getState().set({ kind: 'prompt', title: o.title, body: o.body, initial: o.initial || '', label: o.label || '', confirmLabel: o.confirmLabel || 'OK', resolve })),
};

function DialogHost() {
  const { req, set } = useDialog();
  const [text, setText] = useState('');
  useEffect(() => { if (req?.kind === 'prompt') setText(req.initial); }, [req]);
  if (!req) return null;
  const close = (result: boolean | string | null) => { (req.resolve as (v: any) => void)(result); set(null); };
  const cancel = () => close(req.kind === 'confirm' ? false : null);
  return (
    <Modal title={req.title} onClose={cancel}>
      <form onSubmit={e => { e.preventDefault(); close(req.kind === 'confirm' ? true : text); }} className="space-y-3">
        {req.body && <p className="text-sm text-zinc-400">{req.body}</p>}
        {req.kind === 'prompt' && <input className={inputCls} value={text} onChange={e => setText(e.target.value)} aria-label={req.label || req.title} />}
        <div className="flex justify-end gap-2">
          <Btn onClick={cancel}>Cancel</Btn>
          <Btn type="submit" kind={req.kind === 'confirm' && req.danger ? 'danger' : 'primary'}>{req.confirmLabel}</Btn>
        </div>
      </form>
    </Modal>
  );
}

/** Mount once, near the root. */
export function FeedbackHost() { return <><Toaster /><DialogHost /></>; }
