import { useEffect, useState } from 'react';
import { onDesktopEvent } from './desktop';
import { addLinkDialog, firstUrl, saveLink } from './links';

/** Drop a link onto the window to save it; the tray's "Save link from clipboard" lands here too. */
export default function Links() {
  const [over, setOver] = useState(false);
  useEffect(() => {
    const has = (e: DragEvent) => Array.from(e.dataTransfer?.types || []).some(t => t === 'text/uri-list' || t === 'text/plain');
    const enter = (e: DragEvent) => { if (has(e)) { e.preventDefault(); setOver(true); } };
    const leave = (e: DragEvent) => { if (!e.relatedTarget) setOver(false); };
    const drop = (e: DragEvent) => {
      if (!has(e)) return;
      e.preventDefault(); setOver(false);
      const url = firstUrl(e.dataTransfer?.getData('text/uri-list')) || firstUrl(e.dataTransfer?.getData('text/plain'));
      if (url) saveLink(url); else addLinkDialog();
    };
    window.addEventListener('dragenter', enter); window.addEventListener('dragover', enter); window.addEventListener('dragleave', leave); window.addEventListener('drop', drop);
    let off = () => {}; onDesktopEvent('save-clipboard', () => addLinkDialog()).then(f => { off = f; });
    const open = () => addLinkDialog(); window.addEventListener('sw-add-link', open);
    return () => { window.removeEventListener('dragenter', enter); window.removeEventListener('dragover', enter); window.removeEventListener('dragleave', leave); window.removeEventListener('drop', drop); window.removeEventListener('sw-add-link', open); off(); };
  }, []);
  return over ? <div className="pointer-events-none fixed inset-0 z-40 m-3 flex items-center justify-center rounded-2xl border-2 border-dashed border-indigo-400 bg-indigo-500/10 text-lg" role="status">Drop to save this page to SmartWard</div> : null;
}
