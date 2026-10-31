import { useState } from 'react';
import { ago, del, errText, post, put } from '../api';
import { ask, toast } from '../feedback';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Err, Field, inputCls } from '../ui';

const EVIDENCE: [string, string][] = [['any', 'Any article'], ['claimed', 'Claims or measurements'], ['measured', 'Measured results only']];

/** Saved rules checked against every new article and development; matches show here, on the desktop, and on your phone if you turned that on. */
export default function Watches() {
  const { data, reload } = useLoad<any>('/watches', undefined, 120000);
  const { data: domains } = useLoad<any[]>('/domains');
  const { openArticle } = useNav();
  const [adding, setAdding] = useState(false); const [err, setErr] = useState('');
  const [form, setForm] = useState({ name: '', terms: '', domains: [] as string[], min_evidence: 'any' });
  const list: any[] = data?.watches || [];
  const add = async () => {
    setErr('');
    try { await post('/watches', { ...form, terms: form.terms.split(',').map(t => t.trim()).filter(Boolean) }); setForm({ name: '', terms: '', domains: [], min_evidence: 'any' }); setAdding(false); reload(); }
    catch (e) { setErr(errText(e)); }
  };
  const act = async (fn: () => Promise<any>) => { try { await fn(); reload(); } catch (e) { toast.error(errText(e)); } };
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2"><h2 className="text-base font-semibold">Watches</h2>
        <span className="text-xs text-zinc-500">Tell me when these show up.</span>
        <span className="ml-auto"><Btn small onClick={() => setAdding(!adding)}>{adding ? 'Cancel' : '+ New watch'}</Btn></span></div>
      {adding && <div className="space-y-2 rounded-lg border border-zinc-800 p-3">
        <Field label="Words (comma between; any one matches, whole words, any case)"><input className={inputCls} value={form.terms} onChange={e => setForm({ ...form, terms: e.target.value })} placeholder="sglang, vllm" /></Field>
        <div className="text-sm"><div className="mb-1 text-xs text-zinc-400">Only in these domains (optional)</div>
          <div className="flex flex-wrap gap-2">{(domains || []).map(d => <label key={d.id} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={form.domains.includes(d.name)}
            onChange={e => setForm({ ...form, domains: e.target.checked ? [...form.domains, d.name] : form.domains.filter(x => x !== d.name) })} />{d.name}</label>)}</div></div>
        <div className="flex flex-wrap gap-2">
          <Field label="Name (optional)"><input className={inputCls} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Serving engines" /></Field>
          <Field label="Evidence"><select className={inputCls} value={form.min_evidence} onChange={e => setForm({ ...form, min_evidence: e.target.value })}>{EVIDENCE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field></div>
        <Err>{err}</Err>
        <Btn kind="primary" onClick={add} disabled={!form.terms.trim() && !form.domains.length}>Save watch</Btn>
        <p className="text-xs text-zinc-500">A new watch shows the last two weeks of matches straight away; only newer ones are announced.</p>
      </div>}
      {list.length === 0 && !adding && <p className="text-sm text-zinc-500">No watches yet. For example: “sglang, vllm” in Speculative decoding, measured results only.</p>}
      <ul className="space-y-2">{list.map(w => (
        <li key={w.id} className="rounded-lg border border-zinc-800 p-2">
          <div className="flex flex-wrap items-center gap-2 text-sm"><span className={w.enabled ? 'font-medium' : 'font-medium text-zinc-500'}>{w.name}</span>
            {w.domains.map((d: string) => <Badge key={d}>{d}</Badge>)}{w.min_evidence !== 'any' && <Badge tone="indigo">{w.min_evidence === 'measured' ? 'measured only' : 'claims or measured'}</Badge>}
            <span className="text-xs text-zinc-500">{w.count} match{w.count === 1 ? '' : 'es'}{w.last_hit ? ` · latest ${ago(w.last_hit)}` : ''}</span>
            <span className="ml-auto flex gap-1"><Btn small kind="ghost" onClick={() => act(() => put(`/watches/${w.id}`, { enabled: !w.enabled }))}>{w.enabled ? 'Pause' : 'Resume'}</Btn>
              <Btn small kind="ghost" onClick={async () => { if (await ask.confirm({ title: `Remove “${w.name}”?`, confirmLabel: 'Remove', danger: true })) act(() => del(`/watches/${w.id}`)); }}>Remove</Btn></span></div>
          {w.hits.length > 0 && <ul className="mt-1 space-y-0.5">{w.hits.map((x: any) => (
            <li key={x.article_id} className="truncate text-xs"><button className="text-left text-indigo-300 hover:underline" onClick={() => openArticle(x.article_id)}>{x.title}</button>
              <span className="text-zinc-500"> · {x.source} · {ago(x.ts)}{x.claim ? ` · ${x.evidence}: ${x.claim}` : ''}</span></li>))}</ul>}
        </li>))}</ul>
    </Card>
  );
}
