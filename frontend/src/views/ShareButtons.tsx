import { useState } from 'react';
import { BASE, errText, get } from '../api';
import { toast } from '../feedback';
import { Btn, Modal, inputCls } from '../ui';

/** "Copy for Confluence" and downloads for a memo or a project's implications. Private material is left out by the server. */
export default function ShareButtons({ kind, id }: { kind: 'memo' | 'project'; id: number }) {
  const [fallback, setFallback] = useState(''); const [open, setOpen] = useState(false);
  const url = (format: string) => `${BASE}/api/export/share/${kind}/${id}?format=${format}&download=true`;
  const copy = async () => {
    // The clipboard is written in the same moment as the click (WebKit refuses it once the click is "used up" by a wait), with the text
    // arriving as it loads. Rich text pastes as headings, lists and links in Confluence's editor; plain text is Markdown for everywhere else.
    const h = get(`/export/share/${kind}/${id}`, { format: 'html' }), md = get(`/export/share/${kind}/${id}`, { format: 'markdown' });
    const blob = (p: Promise<any>, type: string) => p.then(r => new Blob([r.content], { type }));
    let copied = false;
    try { await navigator.clipboard.write([new ClipboardItem({ 'text/html': blob(h, 'text/html'), 'text/plain': blob(md, 'text/plain') })]); copied = true; } catch { /* below */ }
    try {
      const [hr, mr] = await Promise.all([h, md]);
      const note = hr.left_out ? ` (${hr.left_out} private citation${hr.left_out === 1 ? '' : 's'} left out)` : '';
      if (copied) toast.ok('Copied. Paste it into a Confluence page' + note);
      else setFallback(mr.content);
    } catch (e) { toast.error(errText(e)); }
  };
  return (
    <>
      <Btn small onClick={copy} title="Copies a formatted version for a Confluence page; private material is never included">Copy for Confluence</Btn>
      <span className="relative">
        <Btn small onClick={() => setOpen(!open)} label="Download">⤓</Btn>
        {open && <span className="absolute right-0 z-20 mt-1 flex w-56 flex-col rounded-lg border border-zinc-700 bg-zinc-900 p-1 text-sm shadow-lg" onMouseLeave={() => setOpen(false)}>
          {([['markdown', 'Markdown (.md)'], ['html', 'Web page (.html)'], ['confluence', 'Confluence source (.xml)']] as const).map(([f, label]) =>
            <a key={f} className="rounded px-2 py-1.5 hover:bg-zinc-800" href={url(f)} download onClick={() => setOpen(false)}>{label}</a>)}
          <span className="px-2 pb-1 pt-0.5 text-[11px] text-zinc-500">Confluence source goes in the page’s source editor (Insert → Markup).</span>
        </span>}
      </span>
      {fallback && <Modal title="Copy this" onClose={() => setFallback('')} wide>
        <p className="mb-2 text-xs text-zinc-500">The clipboard isn’t available here. Select all and copy.</p>
        <textarea className={inputCls + ' h-72 font-mono text-xs'} readOnly value={fallback} onFocus={e => e.currentTarget.select()} />
      </Modal>}
    </>
  );
}
