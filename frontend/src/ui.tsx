import { ReactNode, useEffect, useId, useRef } from 'react';

export const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ');

export function Btn({ children, onClick, kind = 'default', disabled, small, title, type = 'button', loading, label }:
  { children: ReactNode; onClick?: () => void; kind?: 'default' | 'primary' | 'danger' | 'ghost'; disabled?: boolean; small?: boolean; title?: string; type?: 'button' | 'submit'; loading?: boolean; label?: string }) {
  const base = 'inline-flex items-center gap-1.5 rounded-lg font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ' + (small ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-2 text-sm');
  const k = { default: 'bg-zinc-800 hover:bg-zinc-700 border border-zinc-700', primary: 'bg-indigo-600 hover:bg-indigo-500 text-white', danger: 'bg-red-900/60 hover:bg-red-800 border border-red-800', ghost: 'hover:bg-zinc-800 text-zinc-300' }[kind];
  return <button type={type} title={title} aria-label={label} aria-busy={loading || undefined} disabled={disabled || loading} onClick={onClick} className={cx(base, k)}>{loading && <Spin />}{children}</button>;
}
export const Card = ({ children, className }: { children: ReactNode; className?: string }) =>
  <div className={cx('rounded-xl border border-zinc-800 bg-zinc-900/60 p-4', className)}>{children}</div>;
export const Badge = ({ children, tone = 'zinc' }: { children: ReactNode; tone?: 'zinc' | 'green' | 'amber' | 'red' | 'indigo' }) =>
  <span className={cx('inline-block rounded-full px-2 py-0.5 text-[11px]', { zinc: 'bg-zinc-800 text-zinc-300', green: 'bg-emerald-900/50 text-emerald-300', amber: 'bg-amber-900/50 text-amber-300', red: 'bg-red-900/50 text-red-300', indigo: 'bg-indigo-900/60 text-indigo-200' }[tone])}>{children}</span>;
export const Empty = ({ icon = '◌', title, children }: { icon?: string; title: string; children?: ReactNode }) =>
  <div className="mx-auto max-w-sm py-16 text-center"><div className="mb-3 text-3xl text-zinc-600" aria-hidden>{icon}</div><div className="mb-1 text-zinc-200">{title}</div><div className="text-sm text-zinc-500">{children}</div></div>;
export const Err = ({ children }: { children: ReactNode }) => children ? <div role="alert" className="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">{children}</div> : null;
export const Spin = () => <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-zinc-600 border-t-indigo-400" role="status" aria-label="Loading" />;
export const Progress = ({ value, label }: { value: number; label?: string }) => (
  <div className="w-full"><div className="h-1.5 overflow-hidden rounded bg-zinc-800" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value)} aria-label={label || 'Progress'}><div className="h-full bg-indigo-500 transition-all" style={{ width: `${Math.max(2, Math.min(100, value))}%` }} /></div>{label && <div className="mt-1 text-xs text-zinc-500">{label}</div>}</div>
);

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** A dialog: Esc closes it, Tab stays inside it, and focus goes back to where it was. */
export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null); const titleId = useId();
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const first = node?.querySelector<HTMLElement>('input, textarea, select') || node?.querySelector<HTMLElement>('button[type=submit]') || node?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
      if (e.key !== 'Tab' || !node) return;
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (!items.length) return;
      const [a, z] = [items[0], items[items.length - 1]];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => { document.removeEventListener('keydown', onKey, true); before?.focus?.(); };
  }, []);
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} className={cx('max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-900 p-5', wide ? 'max-w-3xl' : 'max-w-lg')} onClick={e => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between"><h3 id={titleId} className="text-base font-semibold">{title}</h3><button onClick={onClose} className="text-zinc-500 hover:text-zinc-200" aria-label="Close">✕</button></div>
        {children}
      </div>
    </div>
  );
}
export const Field = ({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) =>
  <label className="block"><span className="mb-1 block text-xs font-medium text-zinc-400">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-zinc-500">{hint}</span>}</label>;
export const inputCls = 'w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm outline-none focus:border-indigo-500';
export const Seg = ({ value, options, onChange, label }: { value: string; options: [string, string][]; onChange: (v: string) => void; label?: string }) => (
  <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-zinc-700 bg-zinc-900 p-0.5">{options.map(([v, l]) =>
    <button key={v} role="radio" aria-checked={value === v} onClick={() => onChange(v)} className={cx('rounded-md px-3 py-1 text-xs', value === v ? 'bg-zinc-700 text-zinc-50' : 'text-zinc-400 hover:text-zinc-200')}>{l}</button>)}</div>
);
export const Title = ({ children, right }: { children: ReactNode; right?: ReactNode }) =>
  <div className="mb-4 flex items-center justify-between"><h1 className="text-xl font-semibold">{children}</h1><div className="flex items-center gap-2">{right}</div></div>;
