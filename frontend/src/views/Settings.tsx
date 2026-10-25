import { useEffect, useRef, useState } from 'react';
import { BASE, errText, get, post, put, http } from '../api';
import { useLoad } from '../hooks';
import { Badge, Btn, Card, Err, Field, inputCls, Seg, Spin, Title } from '../ui';
import { ask, toast } from '../feedback';
import VoiceSettings from './VoiceSettings';
import DesktopSettings from './DesktopSettings';
import { readPref, setPref, ThemePref } from '../theme';

const slug = (t: string) => t.toLowerCase().replace(/[^a-z]+/g, '-').replace(/^-|-$/g, '');
const SECTIONS = ['Appearance', 'Model', 'Interests & relevance', 'Usage & budget', 'Background refresh', 'Voice', 'Desktop', 'App lock', 'GitHub', 'Export', 'Backup & restore', 'Developer'];
const Section = ({ title, children, desc }: { title: string; children: any; desc?: string }) => <Card className="space-y-3"><div id={slug(title)} className="scroll-mt-16"><h2 className="font-medium">{title}</h2>{desc && <div className="text-xs text-zinc-500">{desc}</div>}</div>{children}</Card>;
const Row = ({ children }: { children: any }) => <div className="flex flex-wrap items-center justify-between gap-2 text-sm">{children}</div>;
const money = (n: number) => '$' + (n || 0).toFixed(n < 1 ? 3 : 2);

export default function Settings() {
  const { data: s, reload } = useLoad<any>('/settings');
  const { data: usage, reload: reloadUsage } = useLoad<any>('/usage', undefined, 10000);
  const { data: models, reload: reloadModels } = useLoad<any>('/models');
  const { data: info, reload: reloadInfo } = useLoad<any>('/dev/info', undefined, 5000);
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('');
  const [local, setLocal] = useState<any>({});
  const save = async (values: any) => { setErr(''); try { await put('/settings', { values }); await reload(); toast.ok('Saved'); } catch (e) { setErr(errText(e)); } };
  const v = (k: string) => (k in local ? local[k] : s?.[k]);
  const set = (k: string, val: any) => setLocal({ ...local, [k]: val });
  if (!s) return <div className="p-6"><Spin /></div>;
  const p = info?.pipeline || {};

  return (
    <div className="h-full overflow-y-auto"><div className="mx-auto max-w-2xl space-y-4 p-5">
      <Title right={<span className="text-xs text-emerald-400" role="status">{msg}</span>}>Settings</Title><Err>{err}</Err>
      <nav aria-label="Settings sections" className="sticky top-0 z-10 -mx-1 flex flex-wrap gap-1 bg-zinc-950/90 px-1 py-2 backdrop-blur">{SECTIONS.map(t => <a key={t} href={'#' + slug(t)} onClick={e => { e.preventDefault(); document.getElementById(slug(t))?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }} className="rounded-full border border-zinc-800 px-2.5 py-0.5 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100">{t}</a>)}</nav>

      <Appearance />

      <Section title="Model" desc="SmartWard runs on a local Ollama model. You can instead bring your own key for a cloud model.">
        <Field label="Chat model"><div className="flex gap-2"><select className={inputCls} value={(models?.ollama || []).some((m: string) => 'ollama_chat/' + m === v('model')) ? v('model') : '__custom'} onChange={e => e.target.value !== '__custom' && save({ model: e.target.value })}>
          {(models?.ollama || []).map((m: string) => <option key={m} value={'ollama_chat/' + m}>Ollama · {m}</option>)}<option value="__custom">Other (type below)…</option></select></div></Field>
        <Field label="Other model (advanced)" hint="Any litellm model id, e.g. ollama_chat/qwen2.5:7b, gpt-4o, anthropic/claude-sonnet-4-5, openrouter/…"><div className="flex gap-2"><input className={inputCls} value={v('model') || ''} onChange={e => set('model', e.target.value)} /><Btn onClick={() => save({ model: v('model') })}>Use</Btn></div></Field>
        <Field label="Embedding model (Ollama)"><div className="flex gap-2"><input className={inputCls} value={v('embed_model') || ''} onChange={e => set('embed_model', e.target.value)} /><Btn onClick={() => save({ embed_model: v('embed_model') })}>Use</Btn></div></Field>
        <Field label="API key for a cloud model (stored on this device, never shown again)"><div className="flex gap-2"><input type="password" className={inputCls} placeholder={s.api_key ? '•••••••• (saved)' : 'sk-…'} value={local.api_key || ''} onChange={e => set('api_key', e.target.value)} /><Btn onClick={() => { save({ api_key: local.api_key }); set('api_key', ''); }} disabled={!local.api_key}>Save</Btn>{s.api_key && <Btn kind="danger" onClick={() => save({ api_key: '' })}>Remove</Btn>}</div></Field>
        <Row><span>Ollama</span><span className="flex items-center gap-2">{models?.ollama_up ? <Badge tone="green">Running · {models.ollama.length} models</Badge> : <Badge tone="red">Not reachable</Badge>}<Btn small onClick={async () => { const m = await get('/models'); (m.ollama_up ? toast.ok(`Ollama is running with ${m.ollama.length} models`) : toast.error('Ollama isn’t reachable. Start it with “ollama serve”.')); reloadModels(); }}>Test connection</Btn></span></Row>
      </Section>

      <Section title="Interests & relevance" desc="Articles are scored against these and your projects, on this device. About 30% already means a match.">
        <textarea className={inputCls} rows={3} value={v('interests') || ''} onChange={e => set('interests', e.target.value)} />
        <Row><span>Filter strictness</span><Seg value={v('strictness')} onChange={x => save({ strictness: x })} options={[['loose', 'Loose 12%'], ['balanced', 'Balanced 22%'], ['strict', 'Strict 32%']]} /></Row>
        <div className="flex justify-end"><Btn onClick={() => save({ interests: v('interests') })}>Save interests</Btn></div>
      </Section>

      <Section title="Usage & budget" desc="Local models cost nothing. A daily budget switches background work back to the local model once your cloud spend is used up.">
        <div className="grid grid-cols-3 gap-2 text-center">{(['today', '7d', '30d'] as const).map(k => <div key={k} className="rounded-lg bg-zinc-800 p-2"><div className="text-xs text-zinc-500">{k === 'today' ? 'Today' : k === '7d' ? '7 days' : '30 days'}</div><div className="text-lg">{money(usage?.[k]?.cost)}</div><div className="text-[11px] text-zinc-500">{usage?.[k]?.calls ?? 0} calls</div></div>)}</div>
        {usage && usage.budget > 0 && <div><div className="h-2 overflow-hidden rounded bg-zinc-800"><div className="h-full bg-indigo-500" style={{ width: Math.min(100, (usage.spent_today / usage.budget) * 100) + '%' }} /></div><div className="mt-1 text-xs text-zinc-500">{money(usage.spent_today)} of {money(usage.budget)} daily cap</div></div>}
        <Row><span>Daily budget ($)</span><div className="flex gap-2"><input type="number" step="0.25" min="0" className={inputCls + ' w-24'} value={v('daily_budget') ?? 1} onChange={e => set('daily_budget', e.target.value)} /><Btn onClick={() => save({ daily_budget: Number(v('daily_budget')) })}>Set</Btn></div></Row>
        {usage?.by_feature?.length > 0 && <table className="w-full text-xs"><thead className="text-left text-zinc-500"><tr><th>Feature</th><th>Calls</th><th>Tokens</th><th className="text-right">Cost</th></tr></thead><tbody>{usage.by_feature.map((f: any) => <tr key={f.feature} className="border-t border-zinc-800"><td className="py-1">{f.feature}</td><td>{f.calls}</td><td>{f.tokens}</td><td className="text-right">{money(f.cost)}</td></tr>)}</tbody></table>}
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={!!s.auto_approve} onChange={e => save({ auto_approve: e.target.checked })} /><span>Approve fetches and new sources automatically<span className="block text-xs text-zinc-500">Applies to every chat and is still logged as auto-approved. Saving a decision or open item always asks.</span></span></label>
      </Section>

      <Section title="Background refresh" desc="While SmartWard is running it checks your sources and indexes new articles. Close it and nothing runs.">
        <Row><span>Check sources every</span><div className="flex gap-2"><select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1" value={s.refresh_minutes} onChange={e => save({ refresh_minutes: Number(e.target.value) })}>{[15, 30, 60, 120, 360].map(m => <option key={m} value={m}>{m < 60 ? m + ' min' : m / 60 + ' h'}</option>)}</select><Btn onClick={async () => { await post('/refresh'); setMsg('Refreshing…'); reloadInfo(); }}>Refresh now</Btn></div></Row>
        <div className="space-y-1 rounded-lg bg-zinc-800/60 p-3 text-sm">
          <div>{p.running ? <><Spin /> {p.step || 'Working'}… {p.done}/{p.total}</> : 'Idle'}{p.last_run ? <span className="text-zinc-500"> · last run {new Date(p.last_run * 1000).toLocaleTimeString()}</span> : ''}</div>
          <div className="text-zinc-400">Waiting to be indexed: {p.waiting ?? 0} · waiting for the graph: {p.graph_waiting ?? 0} · left out of the graph after two tries: {p.graph_left_out ?? 0} · couldn’t be indexed: {p.failed ?? 0}</div>
          {p.last_error && <div className="text-xs text-amber-500">Last problem: {p.last_error}</div>}
          <div className="pt-1"><Btn small onClick={() => post('/pipeline/run').then(reloadInfo)} disabled={p.running}>Index now</Btn></div></div>
      </Section>

      <VoiceSettings s={s} save={save} />

      <DesktopSettings />

      <Lock s={s} onChanged={reload} save={save} />

      <Section title="GitHub" desc="Repo links sync docs and manifests read-only; SmartWard never writes back to GitHub.">
        <Field label="Personal access token (read-only scope)" hint="Only needed for private repos. Private repo content is kept on this device and never sent to a cloud model."><div className="flex gap-2"><input type="password" className={inputCls} placeholder={s.github_token ? '•••••••• (saved)' : 'ghp_…'} value={local.github_token || ''} onChange={e => set('github_token', e.target.value)} /><Btn onClick={() => { save({ github_token: local.github_token }); set('github_token', ''); }} disabled={!local.github_token}>Save</Btn>{s.github_token && <Btn kind="danger" onClick={() => save({ github_token: '' })}>Remove</Btn>}</div></Field>
      </Section>

      <Exports />
      <Backup />

      <Section title="Developer">
       <details><summary className="cursor-pointer text-sm text-zinc-400">Show developer details</summary><div className="mt-3 space-y-3">
        <div className="text-xs text-zinc-500">Data folder: <code>{info?.db}</code></div>
        <div className="flex flex-wrap gap-1.5 text-xs">{Object.entries(info?.counts || {}).map(([k, n]) => <Badge key={k}>{k} {String(n)}</Badge>)}</div>
        {info?.failed_articles?.length > 0 && <details className="text-xs text-zinc-400"><summary className="cursor-pointer">Articles that failed ({info.failed_articles.length})</summary>{info.failed_articles.map((a: any) => <div key={a.id} className="py-0.5">{a.title} — <span className="text-amber-500">{a.stage_error}</span></div>)}</details>}
        <Btn kind="danger" small onClick={async () => { if ((await ask.prompt({ title: 'Erase the whole library?', body: 'This removes every article, project and chat from this computer. Your settings stay. Type erase to confirm.', label: 'Type erase', confirmLabel: 'Erase' })) === 'erase') { await post('/danger/erase', { confirm: 'erase' }); reloadInfo(); reloadUsage(); setMsg('Erased'); } }}>Erase library…</Btn>
       </div></details>
      </Section>
    </div></div>
  );
}

function Lock({ s, onChanged, save }: { s: any; onChanged: () => void; save: (v: any) => void }) {
  const [pin, setPin] = useState(''); const [cur, setCur] = useState(''); const [err, setErr] = useState(''); const [ok, setOk] = useState('');
  const apply = async (remove = false) => { setErr(''); try { await post('/lock/set', { pin: remove ? '' : pin, current: cur }); setPin(''); setCur(''); setOk(remove ? 'Lock removed' : 'Lock set'); onChanged(); } catch (e) { setErr(errText(e)); } };
  return (
    <Section title="App lock" desc="Covers the whole app with a PIN, on launch and after you’ve been away. (No Face ID on this laptop; the PIN is stored as a salted hash.)">
      {s.lock_enabled && <Field label="Current PIN"><input type="password" inputMode="numeric" className={inputCls} value={cur} onChange={e => setCur(e.target.value)} /></Field>}
      <Field label={s.lock_enabled ? 'New PIN' : 'Choose a PIN (4+ digits)'}><input type="password" inputMode="numeric" className={inputCls} value={pin} onChange={e => setPin(e.target.value)} /></Field>
      <Err>{err}</Err>{ok && <div className="text-xs text-emerald-400">{ok}</div>}
      <div className="flex gap-2"><Btn kind="primary" onClick={() => apply(false)} disabled={pin.length < 4}>{s.lock_enabled ? 'Change PIN' : 'Turn on lock'}</Btn>{s.lock_enabled && <Btn kind="danger" onClick={() => apply(true)} disabled={!cur}>Turn off</Btn>}</div>
      {s.lock_enabled && <Row><span>Lock after being away</span><select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1" value={s.lock_after} onChange={e => save({ lock_after: Number(e.target.value) })}>{[[0, 'Immediately'], [60, '1 minute'], [300, '5 minutes'], [900, '15 minutes']].map(([n, l]) => <option key={n} value={n}>{l}</option>)}</select></Row>}
    </Section>
  );
}

function Exports() {
  const [priv, setPriv] = useState(false);
  const a = (path: string) => <a className="inline-flex rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm hover:bg-zinc-700" href={`${BASE}/api/export/${path}${path !== 'markdown' ? `?include_private=${priv}` : ''}`} download>{path === 'json' ? 'Library (JSON)' : path === 'graphml' ? 'Graph (GraphML)' : 'Projects (Markdown)'}</a>;
  return (
    <Section title="Export" desc="Open formats you can keep. GraphML opens in Gephi or yEd.">
      <div className="flex flex-wrap gap-2">{a('json')}{a('graphml')}{a('markdown')}</div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={priv} onChange={e => setPriv(e.target.checked)} />Include private-repo content and themes found only there</label>
    </Section>
  );
}

function Backup() {
  const [pw, setPw] = useState(''); const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [ok, setOk] = useState(''); const file = useRef<HTMLInputElement>(null);
  const doBackup = async () => {
    setBusy(true); setErr(''); setOk('');
    try { const r = await http.post('/backup', { passphrase: pw }, { responseType: 'blob', timeout: 300000 }); const url = URL.createObjectURL(r.data); const a = document.createElement('a'); a.href = url; a.download = 'smartward-backup.swbk'; a.click(); URL.revokeObjectURL(url); setOk('Backup downloaded.'); }
    catch (e: any) { setErr(e?.response?.data instanceof Blob ? JSON.parse(await e.response.data.text()).detail : errText(e)); }
    setBusy(false);
  };
  const doRestore = async (f: File) => {
    if (!(await ask.confirm({ title: 'Restore this backup?', body: 'The current library is erased and replaced by the backup.', confirmLabel: 'Restore', danger: true }))) return;
    setBusy(true); setErr(''); setOk('');
    try { const r = await fetch(`${BASE}/api/restore`, { method: 'POST', body: await f.arrayBuffer(), headers: { 'x-passphrase': pw } }); const j = await r.json(); if (!r.ok) throw new Error(j.detail); setOk(`Restored ${Object.values(j.restored).reduce((a: any, b: any) => a + b, 0)} rows.`); }
    catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <Section title="Backup & restore" desc="The whole library — including private-repo content and embeddings — as one encrypted file (AES-GCM, key from your passphrase with PBKDF2-SHA256, 600,000 rounds). API keys, GitHub token and the app lock are never included.">
      <Field label="Passphrase (8+ characters)"><input type="password" className={inputCls} value={pw} onChange={e => setPw(e.target.value)} /></Field>
      <Err>{err}</Err>{ok && <div className="text-xs text-emerald-400">{ok}</div>}
      <div className="flex gap-2"><Btn onClick={doBackup} disabled={busy || pw.length < 8}>{busy ? <Spin /> : '⬇'} Back up</Btn><Btn onClick={() => file.current?.click()} disabled={busy || pw.length < 8}>⬆ Restore from file…</Btn>
        <input ref={file} type="file" accept=".swbk" hidden onChange={e => { const f = e.target.files?.[0]; if (f) doRestore(f); e.target.value = ''; }} /></div>
      <div className="text-xs text-zinc-500">A wrong passphrase or a damaged file never changes anything.</div>
    </Section>
  );
}

function Appearance() {
  const [pref, setP] = useState<ThemePref>(readPref());
  return (
    <Section title="Appearance" desc="Follow your computer’s light or dark setting, or pick one.">
      <Row><span>Theme</span><Seg value={pref} onChange={(x: string) => { setP(x as ThemePref); setPref(x as ThemePref); }} options={[['system', 'System'], ['light', 'Light'], ['dark', 'Dark']]} /></Row>
    </Section>
  );
}
