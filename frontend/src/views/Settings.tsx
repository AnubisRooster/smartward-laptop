import { useEffect, useRef, useState } from 'react';
import { BASE, errText, get, post, put, http } from '../api';
import { useLoad } from '../hooks';
import { Badge, Btn, Card, Err, Field, inputCls, Seg, Spin, Title } from '../ui';
import { ask, toast } from '../feedback';
import VoiceSettings from './VoiceSettings';
import DesktopSettings from './DesktopSettings';
import { PhonePush, PushDevices } from './PushSettings';
import RemoteSettings from './RemoteSettings';
import { PhoneAccount } from '../RemoteSignIn';
import { openHelp } from '../HelpGuide';
import { readPref, setPref, ThemePref } from '../theme';

const slug = (t: string) => t.toLowerCase().replace(/[^a-z]+/g, '-').replace(/^-|-$/g, '');
const SECTIONS = ['Appearance', 'Notifications', 'Remote access', 'Model', 'Interests & relevance', 'Usage & budget', 'Background refresh', 'Voice', 'Desktop', 'App lock', 'GitHub', 'Export', 'Backup & restore', 'Developer'];
const PHONE_SECTIONS = ['Notifications', 'Usage & budget', 'Model', 'Voice'];      // what a phone may change (the server enforces the same list)
const Section = ({ title, children, desc }: { title: string; children: any; desc?: string }) => <Card className="space-y-3"><div id={slug(title)} className="scroll-mt-16"><h2 className="font-medium">{title}</h2>{desc && <div className="text-xs text-zinc-500">{desc}</div>}</div>{children}</Card>;
const Row = ({ children }: { children: any }) => <div className="flex flex-wrap items-center justify-between gap-2 text-sm">{children}</div>;
const money = (n: number) => '$' + (n || 0).toFixed(n < 1 ? 3 : 2);

export default function Settings({ phone = false }: { phone?: boolean }) {
  const { data: s, reload } = useLoad<any>('/settings');
  const { data: usage, reload: reloadUsage } = useLoad<any>('/usage', undefined, 10000);
  const { data: models, reload: reloadModels } = useLoad<any>('/models');
  const { data: info, reload: reloadInfo } = useLoad<any>(phone ? null : '/dev/info', undefined, 5000);
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('');
  const [local, setLocal] = useState<any>({});
  const save = async (values: any) => { setErr(''); try { await put('/settings', { values }); await reload(); toast.ok('Saved'); } catch (e) { setErr(errText(e)); } };
  const v = (k: string) => (k in local ? local[k] : s?.[k]);
  const set = (k: string, val: any) => setLocal({ ...local, [k]: val });
  if (!s) return <div className="p-6"><Spin /></div>;
  const p = info?.pipeline || {};

  return (
    <div className="h-full overflow-y-auto"><div className="mx-auto max-w-2xl space-y-4 p-5">
      <Title right={<><span className="text-xs text-emerald-400" role="status">{msg}</span><Btn small onClick={() => openHelp()}>Help guide</Btn></>}>Settings</Title><Err>{err}</Err>
      <nav aria-label="Settings sections" className="sticky top-0 z-10 -mx-1 flex flex-wrap gap-1 bg-zinc-950/90 px-1 py-2 backdrop-blur">{(phone ? PHONE_SECTIONS : SECTIONS).map(t => <a key={t} href={'#' + slug(t)} onClick={e => { e.preventDefault(); document.getElementById(slug(t))?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }} className="rounded-full border border-zinc-800 px-2.5 py-0.5 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100">{t}</a>)}</nav>

      {!phone && <Appearance />}
      {phone && <div className="rounded-lg border border-zinc-800 p-3 text-xs text-zinc-500">From your phone you can change the model, the budget and the voice. Everything else, including keys, the app lock, GitHub links and backups, is changed on the laptop.</div>}

      {!phone && <><Section title="Notifications" desc="Desktop notifications while SmartWard is running (it keeps running in the tray when you close the window). With the app lock on, they never show titles.">
        {([['notify_articles', 'New articles that match my interests'], ['notify_sources', 'A source stops refreshing'], ['notify_approvals', 'A chat is waiting for my approval'], ['notify_memo', 'The weekly memo is ready'], ['notify_watches', 'A watch matches something new']] as const).map(([k, label]) =>
          <label key={k} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s[k] !== false} onChange={e => save({ [k]: e.target.checked })} />{label}</label>)}
        <PushDevices />
        <Row><span>Phone notifications per day, at most</span><select aria-label="Phone notifications per day" className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1" value={s.push_daily_cap ?? 6} onChange={e => save({ push_daily_cap: Number(e.target.value) })}>{[2, 4, 6, 10, 20].map(n => <option key={n} value={n}>{n}</option>)}</select></Row>
      </Section></>}
      {phone && <Section title="Notifications" desc="Get a notification on this phone when a watch matches or the weekly memo is ready."><PhonePush /></Section>}

      {!phone && <RemoteSettings />}

      <Section title="Model" desc="SmartWard runs on a local Ollama model. You can instead bring your own key for a cloud model.">
        <Field label="Chat model"><div className="flex gap-2"><select className={inputCls} value={(models?.ollama || []).some((m: string) => 'ollama_chat/' + m === v('model')) ? v('model') : '__custom'} onChange={e => e.target.value !== '__custom' && save({ model: e.target.value })}>
          {(models?.ollama || []).map((m: string) => <option key={m} value={'ollama_chat/' + m}>Ollama · {m}</option>)}<option value="__custom">Other (type below)…</option></select></div></Field>
        <Field label="Other model (advanced)" hint="Any litellm model id, e.g. ollama_chat/qwen2.5:7b, gpt-4o, anthropic/claude-sonnet-4-5, openrouter/…"><div className="flex gap-2"><input className={inputCls} value={v('model') || ''} onChange={e => set('model', e.target.value)} /><Btn onClick={() => save({ model: v('model') })}>Use</Btn></div></Field>
        {!phone && <Field label="Embedding model (Ollama)"><div className="flex gap-2"><input className={inputCls} value={v('embed_model') || ''} onChange={e => set('embed_model', e.target.value)} /><Btn onClick={() => save({ embed_model: v('embed_model') })}>Use</Btn></div></Field>}
        {!phone && <Field label="Design model (architecture drafts)" hint="Empty uses the chat model. Drafting an architecture needs a capable model; any litellm id, e.g. openrouter/anthropic/claude-sonnet-4-5. Private projects always use the local model."><div className="flex gap-2"><input className={inputCls} placeholder="same as the chat model" value={v('design_model') || ''} onChange={e => set('design_model', e.target.value)} /><Btn onClick={() => save({ design_model: (v('design_model') || '').trim() })}>Save</Btn></div></Field>}
        {!phone && <Field label="Review model (checks architecture drafts)" hint="A second model that reviews each draft. Empty: your chat model when another model drafts, else the analysis model. Choose one at least as capable as the design model."><div className="flex gap-2"><input className={inputCls} placeholder="automatic" value={v('review_model') || ''} onChange={e => set('review_model', e.target.value)} /><Btn onClick={() => save({ review_model: (v('review_model') || '').trim() })}>Save</Btn></div></Field>}
        {!phone && <Field label="API key for a cloud model (stored on this device, never shown again)"><div className="flex gap-2"><input type="password" className={inputCls} placeholder={s.api_key ? '•••••••• (saved)' : 'sk-…'} value={local.api_key || ''} onChange={e => set('api_key', e.target.value)} /><Btn onClick={() => { save({ api_key: local.api_key }); set('api_key', ''); }} disabled={!local.api_key}>Save</Btn>{s.api_key && <Btn kind="danger" onClick={() => save({ api_key: '' })}>Remove</Btn>}</div></Field>}
        <OpenRouter s={s} model={v('model') || ''} save={save} />
        <Row><span>Ollama</span><span className="flex items-center gap-2">{models?.ollama_up ? <Badge tone="green">Running · {models.ollama.length} models</Badge> : <Badge tone="red">Not reachable</Badge>}<Btn small onClick={async () => { const m = await get('/models'); (m.ollama_up ? toast.ok(`Ollama is running with ${m.ollama.length} models`) : toast.error('Ollama isn’t reachable. Start it with “ollama serve”.')); reloadModels(); }}>Test connection</Btn></span></Row>
      </Section>

      {!phone && <><Section title="Interests & relevance" desc="Articles are scored against these and your projects, on this device. About 30% already means a match.">
        <textarea className={inputCls} rows={3} value={v('interests') || ''} onChange={e => set('interests', e.target.value)} />
        <Row><span>Filter strictness</span><Seg value={v('strictness')} onChange={x => save({ strictness: x })} options={[['loose', 'Loose 12%'], ['balanced', 'Balanced 22%'], ['strict', 'Strict 32%']]} /></Row>
        <div className="flex justify-end"><Btn onClick={() => save({ interests: v('interests') })}>Save interests</Btn></div>
      </Section></>}

      <Section title="Usage & budget" desc="Local models cost nothing. A daily budget switches background work back to the local model once your cloud spend is used up.">
        <div className="grid grid-cols-3 gap-2 text-center">{(['today', '7d', '30d'] as const).map(k => <div key={k} className="rounded-lg bg-zinc-800 p-2"><div className="text-xs text-zinc-500">{k === 'today' ? 'Today' : k === '7d' ? '7 days' : '30 days'}</div><div className="text-lg">{money(usage?.[k]?.cost)}</div><div className="text-[11px] text-zinc-500">{usage?.[k]?.calls ?? 0} calls</div></div>)}</div>
        {usage && usage.budget > 0 && <div><div className="h-2 overflow-hidden rounded bg-zinc-800"><div className="h-full bg-indigo-500" style={{ width: Math.min(100, (usage.spent_today / usage.budget) * 100) + '%' }} /></div><div className="mt-1 text-xs text-zinc-500">{money(usage.spent_today)} of {money(usage.budget)} daily cap</div></div>}
        <Row><span>Daily budget ($)</span><div className="flex gap-2"><input type="number" step="0.25" min="0" className={inputCls + ' w-24'} value={v('daily_budget') ?? 1} onChange={e => set('daily_budget', e.target.value)} /><Btn onClick={() => save({ daily_budget: Number(v('daily_budget')) })}>Set</Btn></div></Row>
        {usage?.by_feature?.length > 0 && <table className="w-full text-xs"><thead className="text-left text-zinc-500"><tr><th>Feature</th><th>Calls</th><th>Tokens</th><th className="text-right">Cost</th></tr></thead><tbody>{usage.by_feature.map((f: any) => <tr key={f.feature} className="border-t border-zinc-800"><td className="py-1">{f.feature}</td><td>{f.calls}</td><td>{f.tokens}</td><td className="text-right">{money(f.cost)}</td></tr>)}</tbody></table>}
        {!phone && <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={!!s.auto_approve} onChange={e => save({ auto_approve: e.target.checked })} /><span>Approve fetches and new sources automatically<span className="block text-xs text-zinc-500">Applies to every chat and is still logged as auto-approved. Saving a decision or open item always asks.</span></span></label>}
      </Section>

      {!phone && <><Section title="Background refresh" desc="While SmartWard is running it checks your sources and indexes new articles. Close it and nothing runs.">
        <Row><span>Check sources every</span><div className="flex gap-2"><select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1" value={s.refresh_minutes} onChange={e => save({ refresh_minutes: Number(e.target.value) })}>{[15, 30, 60, 120, 360].map(m => <option key={m} value={m}>{m < 60 ? m + ' min' : m / 60 + ' h'}</option>)}</select><Btn onClick={async () => { await post('/refresh'); setMsg('Refreshing…'); reloadInfo(); }}>Refresh now</Btn></div></Row>
        <Row><label className="flex items-center gap-2"><input type="checkbox" checked={!!s.memo_auto} onChange={e => save({ memo_auto: e.target.checked })} />Write the weekly memo on</label>
          <select aria-label="Memo day" className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1" value={s.memo_day ?? 0} disabled={!s.memo_auto} onChange={e => save({ memo_day: Number(e.target.value) })}>{['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((d, i) => <option key={d} value={i}>{d}</option>)}</select></Row>
        <div className="space-y-1 rounded-lg bg-zinc-800/60 p-3 text-sm">
          <div>{p.running ? <><Spin /> {p.step || 'Working'}… {p.done}/{p.total}</> : 'Idle'}{p.last_run ? <span className="text-zinc-500"> · last run {new Date(p.last_run * 1000).toLocaleTimeString()}</span> : ''}</div>
          <div className="text-zinc-400">Waiting to be indexed: {p.waiting ?? 0} · waiting for the graph: {p.graph_waiting ?? 0} · left out of the graph after two tries: {p.graph_left_out ?? 0} · couldn’t be indexed: {p.failed ?? 0}</div>
          {p.last_error && <div className="text-xs text-amber-500">Last problem: {p.last_error}</div>}
          <div className="pt-1"><Btn small onClick={() => post('/pipeline/run').then(reloadInfo)} disabled={p.running}>Index now</Btn></div></div>
      </Section></>}

      <VoiceSettings s={s} save={save} phone={phone} />

      {!phone && <><DesktopSettings />

      <Lock s={s} onChanged={reload} save={save} /></>}

      {!phone && <><Section title="GitHub" desc="Repo links sync docs and manifests read-only; SmartWard never writes back to GitHub.">
        <Field label="Personal access token (read-only scope)" hint="Only needed for private repos. Private repo content is kept on this device and never sent to a cloud model."><div className="flex gap-2"><input type="password" className={inputCls} placeholder={s.github_token ? '•••••••• (saved)' : 'ghp_…'} value={local.github_token || ''} onChange={e => set('github_token', e.target.value)} /><Btn onClick={() => { save({ github_token: local.github_token }); set('github_token', ''); }} disabled={!local.github_token}>Save</Btn>{s.github_token && <Btn kind="danger" onClick={() => save({ github_token: '' })}>Remove</Btn>}</div></Field>
      </Section></>}

      {!phone && <><Exports />
      <Backup /></>}

      {!phone && <><Section title="Developer">
       <details><summary className="cursor-pointer text-sm text-zinc-400">Show developer details</summary><div className="mt-3 space-y-3">
        <div className="text-xs text-zinc-500">Data folder: <code>{info?.db}</code></div>
        <div className="flex flex-wrap gap-1.5 text-xs">{Object.entries(info?.counts || {}).map(([k, n]) => <Badge key={k}>{k} {String(n)}</Badge>)}</div>
        {info?.failed_articles?.length > 0 && <details className="text-xs text-zinc-400"><summary className="cursor-pointer">Articles that failed ({info.failed_articles.length})</summary>{info.failed_articles.map((a: any) => <div key={a.id} className="py-0.5">{a.title} — <span className="text-amber-500">{a.stage_error}</span></div>)}</details>}
        <Btn kind="danger" small onClick={async () => { if ((await ask.prompt({ title: 'Erase the whole library?', body: 'This removes every article, project and chat from this computer. Your settings stay. Type erase to confirm.', label: 'Type erase', confirmLabel: 'Erase' })) === 'erase') { await post('/danger/erase', { confirm: 'erase' }); reloadInfo(); reloadUsage(); setMsg('Erased'); } }}>Erase library…</Btn>
       </div></details>
      </Section></>}
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
      {s.lock_enabled && <Row><span>Lock after leaving the window for</span><select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1" value={s.lock_after} onChange={e => save({ lock_after: Number(e.target.value) })}>{[[0, 'Immediately'], [60, '1 minute'], [300, '5 minutes'], [900, '15 minutes']].map(([n, l]) => <option key={n} value={n}>{l}</option>)}</select></Row>}
      {s.lock_enabled && <Row><span>Lock after no activity <span className="block text-xs text-zinc-500">Typing, clicking, scrolling, moving the mouse, hands-free talking and waiting for an answer all count as activity.</span></span><select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1" value={s.lock_idle} onChange={e => save({ lock_idle: Number(e.target.value) })}>{[[0, 'Never'], [5, '5 minutes'], [15, '15 minutes'], [30, '30 minutes'], [60, '1 hour']].map(([n, l]) => <option key={n} value={n}>{l}</option>)}</select></Row>}
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

function OpenRouter({ s, model, save }: { s: any; model: string; save: (v: any) => Promise<void> }) {
  const [list, setList] = useState<any[] | null>(null); const [q, setQ] = useState(''); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const current = model.startsWith('openrouter/');
  const load = async (refresh = false) => { setBusy(true); setErr(''); try { setList((await get('/openrouter/models', { refresh })).models); } catch (e) { setErr(errText(e)); } setBusy(false); };
  const test = async () => { setBusy(true); try { await post('/models/test'); toast.ok('The model answered.'); } catch (e) { toast.error(errText(e)); } setBusy(false); };
  const shown = (list || []).filter(m => !q.trim() || (m.name + ' ' + m.id).toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <details className="rounded-lg border border-zinc-800 p-3" open={current || undefined}>
      <summary className="cursor-pointer text-sm font-medium">OpenRouter free models{current && <span className="ml-2 text-xs font-normal text-emerald-400">in use: {model.replace('openrouter/', '')}</span>}</summary>
      <div className="mt-3 space-y-3 text-sm">
        <div className="text-xs text-zinc-500">Free models run on OpenRouter’s servers, so what you ask (and any library text the strategist includes) leaves this computer, and free providers may keep it. Private repo content and off-the-record chats always stay on the local model.
          You need an OpenRouter key: create one at <a className="text-indigo-300 underline" href="https://openrouter.ai/keys" target="_blank" rel="noreferrer noopener">openrouter.ai/keys</a> and paste it into “API key” below. Free models are rate-limited.</div>
        <div className="flex flex-wrap items-center gap-2">
          <Btn small onClick={() => load(false)} loading={busy && !list}>{list ? 'Refresh list' : 'Browse free models'}</Btn>
          {list && <input className={inputCls + ' max-w-xs'} placeholder={`Search ${list.length} free models…`} aria-label="Search free models" value={q} onChange={e => setQ(e.target.value)} />}
          {current && <><Btn small onClick={test} loading={busy && !!list}>Test the model</Btn><Btn small kind="ghost" onClick={() => save({ model: 'ollama_chat/llama3.2:3b' })}>Go back to local</Btn></>}
        </div>
        <Err>{err}</Err>
        {list && <ul className="max-h-72 space-y-1 overflow-y-auto" role="listbox" aria-label="Free models">{shown.map(m => (
          <li key={m.id}><button type="button" role="option" aria-selected={model === m.model} onClick={() => save({ model: m.model })}
            className={'w-full rounded-lg border px-3 py-2 text-left ' + (model === m.model ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-800 hover:bg-zinc-900')}>
            <span className="flex items-center justify-between gap-2"><span className="font-medium">{m.name}</span><span className="flex shrink-0 gap-1.5"><Badge>{Math.round(m.context / 1000)}k context</Badge>{m.tools ? <Badge tone="green">tools</Badge> : <Badge tone="amber">no tools</Badge>}</span></span>
            <span className="block truncate text-xs text-zinc-500">{m.id}</span></button></li>))}
          {shown.length === 0 && <li className="text-xs text-zinc-500">No free model matches.</li>}</ul>}
        {list && <div className="text-xs text-zinc-500">“No tools” models can chat but can’t search your library or fetch pages for you.</div>}
        {current && <Row><span>Use it for</span><Seg value={s.cloud_scope || 'analysis'} onChange={x => save({ cloud_scope: x })} options={[['chat', 'Chat only'], ['analysis', 'Chat + analysis'], ['everything', 'Everything']]} /></Row>}
        <Row><span>Analysis model <span className="text-xs text-zinc-500">(reads public articles for the graph and trends)</span></span>
          <select className="max-w-[16rem] rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm" aria-label="Analysis model" value={s.analysis_model || ''} onChange={e => save({ analysis_model: e.target.value })}>
            {!(list || []).some(m => m.model === s.analysis_model) && <option value={s.analysis_model || ''}>{(s.analysis_model || 'None (use the local model)').replace('openrouter/', '')}</option>}
            {(list || []).map(m => <option key={m.id} value={m.model}>{m.name} ({m.id.split('/')[0]})</option>)}<option value="">None (use the local model)</option></select></Row>
        <div className="text-xs text-zinc-500">Pinned to one fast model, three articles at a time. If it is busy, {(s.analysis_fallbacks || []).map((f: string) => f.replace('openrouter/', '')).join(', ') || 'the fallback'} is tried next, and the batch waits politely when every model is rate-limited. Browse the list above to change it.</div>
        {current && <div className="text-xs text-zinc-500">“Chat + analysis” also uses it to read public articles for the knowledge graph and trend analysis. “Chat only” keeps all of that on the local model. Private content never leaves this computer in any mode.</div>}
      </div>
    </details>
  );
}

/** Settings as a phone sees it: this phone (theme, sign out), then the parts a phone may change. */
export function PhoneSettings() {
  return <div className="h-full overflow-y-auto"><PhoneAccount embedded /><div className="-mt-4"><Settings phone /></div></div>;
}
