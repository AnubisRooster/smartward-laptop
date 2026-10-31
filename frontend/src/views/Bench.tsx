import { useEffect, useState } from 'react';
import { ago, del, errText, get, post } from '../api';
import { onPhone } from '../device';
import { toast } from '../feedback';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Err, Modal, Spin } from '../ui';

const STATUS: Record<string, [string, 'green' | 'amber' | 'red' | 'indigo' | 'zinc']> = {
  proposed: ['Waiting for your approval', 'indigo'], running: ['Running', 'amber'], done: ['Measured', 'green'], failed: ['Failed', 'red'],
  not_testable: ['Can’t be tested here', 'zinc'], rejected: ['Script not usable', 'red'] };
const TESTABLE: Record<string, string> = { yes: 'Tests the claim', proxy: 'A related measurement, not the claim itself', no: 'Not testable on this laptop' };

/** One test: the plan and the script to read, then approval to download a model and to run. */
export function BenchRun({ id, onClose }: { id: number; onClose: () => void }) {
  const [r, setR] = useState<any>(null); const [err, setErr] = useState(''); const [busy, setBusy] = useState('');
  const { openArticle } = useNav();
  const load = () => get(`/bench/${id}`).then(setR).catch(e => setErr(errText(e)));
  useEffect(() => { load(); }, [id]);
  const waiting = r && (r.status === 'running' || r.missing?.some((m: any) => m.pull === 'downloading'));
  useEffect(() => { if (!waiting) return; const t = setInterval(load, 3000); return () => clearInterval(t); }, [waiting]);
  const act = async (name: string, fn: () => Promise<any>) => { setBusy(name); setErr(''); try { await fn(); await load(); } catch (e) { setErr(errText(e)); } setBusy(''); };
  if (!r) return <Modal title="Test bench" onClose={onClose}>{err ? <Err>{err}</Err> : <Spin />}</Modal>;
  const p = r.plan || {}; const st = STATUS[r.status] || [r.status, 'zinc'];
  return (
    <Modal title="Test bench" onClose={onClose} wide>
      <div className="space-y-3 text-sm">
        <div className="rounded-lg border border-zinc-800 p-2"><div className="text-xs text-zinc-500">The claim ({r.development?.evidence}, {r.development?.source})</div>
          <div>{r.development?.subject}: {r.development?.claim} {r.development && <button className="text-xs text-indigo-300 hover:underline" onClick={() => { onClose(); openArticle(r.development.article_id); }}>Open article</button>}</div></div>
        <div className="flex flex-wrap items-center gap-2"><Badge tone={st[1]}>{st[0]}</Badge>{p.testable && <Badge tone={p.testable === 'yes' ? 'green' : p.testable === 'proxy' ? 'amber' : 'zinc'}>{TESTABLE[p.testable]}</Badge>}
          {p.expected_minutes && r.status === 'proposed' && <span className="text-xs text-zinc-500">about {p.expected_minutes} min</span>}<span className="text-xs text-zinc-500">drafted {ago(r.created)}</span></div>
        {p.plan && <p>{p.plan}</p>}
        {p.why_not && <p className="text-xs text-zinc-400"><span className="font-medium">What this laptop can’t test:</span> {p.why_not}</p>}
        {p.problems?.length > 0 && <ul className="text-xs text-red-300">{p.problems.map((x: string) => <li key={x}>{x}</li>)}</ul>}
        {r.result && <div className="rounded-lg border border-emerald-800 bg-emerald-950/30 p-2"><div className="font-medium">{r.result.metric}: {r.result.value.toPrecision(3)} {r.result.unit}{r.result.baseline != null && <> vs {r.result.baseline.toPrecision(3)} {r.result.unit} {r.result.baseline_label && `(${r.result.baseline_label})`}</>}</div>
          <div className="text-xs text-zinc-400">{r.result.notes} {r.result.runs ? `· ${r.result.runs} runs` : ''} · {r.result.calls} model calls in {r.result.seconds}s. Saved as measured evidence from “Test bench”.</div></div>}
        {r.error && <Err>{r.error}</Err>}
        {r.script && <details open={r.status === 'proposed'}><summary className="cursor-pointer text-xs text-zinc-400">The script ({r.script.split('\n').length} lines). It runs with no network and no access to your files; it can only ask SmartWard to run {p.models?.join(' or ')}.</summary>
          <pre className="mt-1 max-h-72 overflow-auto rounded bg-zinc-950 p-2 text-xs">{r.script}</pre></details>}
        {r.log && <details><summary className="cursor-pointer text-xs text-zinc-400">What it printed</summary><pre className="mt-1 max-h-48 overflow-auto rounded bg-zinc-950 p-2 text-xs">{r.log}</pre></details>}
        <Err>{err}</Err>
        {!onPhone && <div className="flex flex-wrap items-center gap-2">
          {r.missing?.map((m: any) => <Btn key={m.model} onClick={() => act('pull', () => post(`/bench/${id}/pull`, { model: m.model }))} loading={m.pull === 'downloading'} disabled={r.status !== 'proposed' && r.status !== 'failed'}
            title="Downloads the model into Ollama on this laptop">{m.pull === 'downloading' ? `Downloading ${m.model}…` : `Download ${m.model}${m.gb ? ` (about ${m.gb} GB)` : ''}`}</Btn>)}
          {r.missing?.some((m: any) => m.pull?.startsWith('failed')) && <span className="text-xs text-red-300">{r.missing.find((m: any) => m.pull?.startsWith('failed')).pull}</span>}
          {(r.status === 'proposed' || r.status === 'failed') && <Btn kind="primary" onClick={() => act('run', () => post(`/bench/${id}/run`))} loading={busy === 'run'} disabled={r.missing?.length > 0}>{r.status === 'failed' ? 'Run again' : 'Approve and run'}</Btn>}
          {r.status === 'running' && <span className="text-xs text-zinc-400" role="status"><Spin /> Running in the sandbox…</span>}
          {r.status !== 'running' && <Btn kind="ghost" onClick={async () => { await del(`/bench/${id}`); toast.ok('Removed'); onClose(); }}>Remove</Btn>}
        </div>}
        {onPhone && r.status === 'proposed' && <p className="text-xs text-zinc-500">Approve and run it on the laptop.</p>}
      </div>
    </Modal>
  );
}

/** "Test this" next to a development: drafts a test and opens it for review. Laptop only. */
export function TestThis({ devId }: { devId: number }) {
  const [busy, setBusy] = useState(false); const [open, setOpen] = useState<number | null>(null);
  if (onPhone) return null;
  const go = async () => { setBusy(true); try { setOpen((await post('/bench', { development_id: devId })).id); } catch (e) { toast.error(errText(e)); } setBusy(false); };
  return <>
    <button className="ml-1 text-xs text-zinc-500 hover:text-indigo-300 disabled:opacity-50" onClick={go} disabled={busy} title="Draft a test of this claim on this laptop; nothing runs until you approve">{busy ? 'drafting a test…' : '🧪 test this'}</button>
    {open !== null && <BenchRun id={open} onClose={() => setOpen(null)} />}
  </>;
}

/** The Radar's list of tests, newest first. */
export default function BenchCard() {
  const { data, reload } = useLoad<any>('/bench', undefined, 15000);
  const [open, setOpen] = useState<number | null>(null);
  const runs: any[] = data?.runs || [];
  return (
    <Card className="space-y-2">
      <div className="flex flex-wrap items-center gap-2"><h2 className="text-base font-semibold">Test bench</h2>
        <span className="text-xs text-zinc-500">Claims measured on this laptop{data?.machine ? ` (${data.machine.cpu}, ${data.machine.cores} cores, CPU only)` : ''}.</span></div>
      {data && !data.sandbox && <Err>The sandbox isn’t installed, so tests can’t run. Install it with: sudo apt install bubblewrap</Err>}
      {runs.length === 0 ? <p className="text-sm text-zinc-500">No tests yet. Use “🧪 test this” next to a development in a project’s implications or stack map.</p> :
        <ul className="space-y-1.5">{runs.map(r => { const st = STATUS[r.status] || [r.status, 'zinc']; return (
          <li key={r.id}><button className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-zinc-800 p-2 text-left text-sm hover:bg-zinc-800/50" onClick={() => setOpen(r.id)}>
            <Badge tone={st[1]}>{st[0]}</Badge><span className="min-w-0 flex-1 truncate">{r.development?.subject}: {r.development?.claim}</span>
            {r.result && <span className="text-xs text-emerald-300">{r.result.metric}: {r.result.value.toPrecision(3)} {r.result.unit}</span>}<span className="text-xs text-zinc-500">{ago(r.finished || r.created)}</span></button></li>); })}</ul>}
      {open !== null && <BenchRun id={open} onClose={() => { setOpen(null); reload(); }} />}
    </Card>
  );
}
