import { useEffect, useState } from 'react';
import { SHORTCUTS, isTyping, tabForKey } from './shortcuts';
import { useNav } from './hooks';
import { Modal } from './ui';

/** Global single-key shortcuts and the ? overlay. Ignored while typing, and with Ctrl/Alt/Meta held. */
export default function Shortcuts() {
  const { go } = useNav(); const [help, setHelp] = useState(false);
  useEffect(() => { const f = () => setHelp(true); window.addEventListener('sw-help', f); return () => window.removeEventListener('sw-help', f); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented || isTyping(e.target as HTMLElement)) return;
      if (document.querySelector('[role="dialog"]')) return;
      const tab = tabForKey(e.key);
      if (tab) { e.preventDefault(); go(tab); return; }
      if (e.key === '/') { const box = document.querySelector<HTMLElement>('[aria-label="Search"]'); if (box) { e.preventDefault(); box.focus(); } else { e.preventDefault(); go('reading'); setTimeout(() => document.querySelector<HTMLElement>('[aria-label="Search"]')?.focus(), 150); } return; }
      if (e.key === '?') { e.preventDefault(); setHelp(true); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go]);
  if (!help) return null;
  return (
    <Modal title="Keyboard shortcuts" onClose={() => setHelp(false)}>
      <table className="w-full text-sm"><tbody>{SHORTCUTS.map(s => (
        <tr key={s.keys + s.does} className="border-t border-zinc-800 first:border-0"><td className="whitespace-nowrap py-1.5 pr-4"><kbd className="rounded border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 text-xs">{s.keys}</kbd></td><td>{s.does}</td><td className="pl-3 text-right text-xs text-zinc-500">{s.where}</td></tr>))}</tbody></table>
    </Modal>
  );
}
