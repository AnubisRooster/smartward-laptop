import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { errText, get } from './api';
import { Err, Modal, Spin } from './ui';
import { toast } from './feedback';

export const slug = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const textOf = (n: any): string => (typeof n === 'string' ? n : Array.isArray(n) ? n.map(textOf).join('') : n?.props?.children ? textOf(n.props.children) : '');

/** Opens the help guide from anywhere (optionally at a section): `openHelp('voice-reading-aloud-and-talking')`. */
export const openHelp = (anchor?: string) => window.dispatchEvent(new CustomEvent('open-help', { detail: anchor || '' }));

/** Lives once in the app and shows the guide when asked. */
export function HelpHost() {
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { const f = (e: Event) => setOpen(String((e as CustomEvent).detail || '')); window.addEventListener('open-help', f); return () => window.removeEventListener('open-help', f); }, []);
  return open === null ? null : <HelpGuide anchor={open} onClose={() => setOpen(null)} />;
}

function Pre({ children }: { children?: any }) {
  const text = textOf(children).replace(/\n$/, '');
  const copy = async () => { try { await navigator.clipboard.writeText(text); toast.ok('Copied'); } catch { toast.error('Couldn’t copy'); } };
  return <div className="group relative my-3"><pre className="overflow-x-auto rounded-lg bg-zinc-950 p-3 text-xs leading-relaxed text-zinc-200">{children}</pre>
    <button onClick={copy} className="absolute right-2 top-2 rounded border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[11px] text-zinc-300 opacity-70 hover:opacity-100 focus:opacity-100">Copy</button></div>;
}

export default function HelpGuide({ anchor, onClose }: { anchor?: string; onClose: () => void }) {
  const [md, setMd] = useState<string | null>(null); const [err, setErr] = useState('');
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { get('/help').then(r => setMd(r.markdown)).catch(e => setErr(errText(e))); }, []);
  const toc = useMemo(() => (md || '').split('\n').filter(l => l.startsWith('## ')).map(l => l.slice(3).trim()), [md]);
  const go = (a: string) => box.current?.querySelector(`#help-${CSS.escape(a)}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  useEffect(() => { if (md && anchor) setTimeout(() => go(anchor), 60); }, [md]);
  const H = (Tag: 'h1' | 'h2' | 'h3') => ({ children }: any) => <Tag id={`help-${slug(textOf(children))}`} className={Tag === 'h1' ? 'mb-2 text-2xl font-semibold' : Tag === 'h2' ? 'mb-2 mt-7 scroll-mt-2 text-lg font-semibold' : 'mb-1 mt-4 scroll-mt-2 font-medium'}>{children}</Tag>;
  return (
    <Modal title="Help guide" onClose={onClose} wide>
      <Err>{err}</Err>
      {md === null ? (err ? null : <div className="p-4" role="status"><Spin /></div>) : (
        <div className="flex flex-col gap-4 md:flex-row">
          <nav aria-label="Guide sections" className="shrink-0 md:sticky md:top-0 md:w-48 md:self-start"><ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs md:flex-col md:gap-1">
            {toc.map(t => <li key={t}><button className="text-left text-indigo-300 hover:underline" onClick={() => go(slug(t))}>{t}</button></li>)}</ul></nav>
          <div ref={box} className="help-body min-w-0 flex-1 text-sm leading-relaxed text-zinc-300 [&_a]:text-indigo-300 [&_a]:underline [&_code]:rounded [&_code]:bg-zinc-800 [&_code]:px-1 [&_code]:text-[12px] [&_p]:mb-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_ol]:mb-3 [&_ol]:ml-5 [&_ol]:list-decimal [&_ul]:mb-3 [&_ul]:ml-5 [&_ul]:list-disc [&_li]:mb-1 [&_table]:my-3 [&_table]:w-full [&_table]:text-left [&_th]:border-b [&_th]:border-zinc-700 [&_th]:py-1 [&_th]:pr-3 [&_td]:border-b [&_td]:border-zinc-800 [&_td]:py-1.5 [&_td]:pr-3 [&_td]:align-top">
            <ReactMarkdown rehypePlugins={[rehypeSanitize]} components={{ h1: H('h1'), h2: H('h2'), h3: H('h3'), pre: Pre, a: ({ href, children }: any) => <a href={href} target="_blank" rel="noreferrer noopener">{children}</a> }}>{md}</ReactMarkdown>
          </div>
        </div>)}
    </Modal>
  );
}
