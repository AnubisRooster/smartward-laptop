import { useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { errText, get, post, put } from '../api';
import { useLoad } from '../hooks';
import { Badge, Btn, Card, Err, Field, inputCls } from '../ui';
import { toast } from '../feedback';
import { ago } from '../api';

const Step = ({ ok, children }: { ok: boolean | null; children: any }) => <li className="flex items-start gap-2 text-sm"><span aria-hidden className={ok ? 'text-emerald-400' : 'text-zinc-500'}>{ok ? '✓' : '○'}</span><span>{children}</span></li>;

/** Settings → Remote access: reach SmartWard from a phone through your private Tailscale network. Only available on the laptop itself. */
export default function RemoteSettings() {
  const { data: r, reload } = useLoad<any>('/remote/status', undefined, 8000);
  const { data: ts, reload: reloadTs } = useLoad<any>('/remote/tailscale', undefined, 8000);
  const [login, setLogin] = useState(''); const [pass, setPass] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const qr = useRef<HTMLCanvasElement>(null);
  useEffect(() => { if (r && !login) setLogin(r.login || ts?.login || ''); }, [r?.login, ts?.login]);
  useEffect(() => { if (ts?.https_url && qr.current) void QRCode.toCanvas(qr.current, ts.https_url, { width: 144, margin: 1 }).catch(() => {}); }, [ts?.https_url]);
  if (!r) return null;
  const save = async (body: any, ok?: string) => { setErr(''); setBusy(true); try { await put('/remote/config', body); await reload(); if (ok) toast.ok(ok); } catch (e) { setErr(errText(e)); } setBusy(false); };
  const copy = async (t: string) => { try { await navigator.clipboard.writeText(t); toast.ok('Copied'); } catch { toast.error('Couldn’t copy'); } };
  const url = r.host ? `https://${r.host}` : ts?.https_url || '';
  return (
    <Card className="space-y-3">
      <div id="remote-access" className="scroll-mt-16"><h2 className="font-medium">Remote access (phone)</h2>
        <div className="text-xs text-zinc-500">Open SmartWard from your Android phone or iPhone in its browser, over your private Tailscale network. It is never on the public internet, and you add it to the Home Screen like an app (no app store). Your laptop must be awake and running SmartWard.</div></div>
      <Err>{err}</Err>

      <ol className="space-y-1.5">
        <Step ok={ts?.installed ?? null}>Install <a className="text-indigo-300 underline" href="https://tailscale.com/download" target="_blank" rel="noreferrer noopener">Tailscale</a> on this laptop and on your phone, and sign in to the same account on both.</Step>
        <Step ok={ts?.installed ? ts.state === 'Running' : null}>Tailscale is running here{ts?.installed && ts.state !== 'Running' ? ` (it says: ${ts.state})` : ''}. In the Tailscale admin page, turn on MagicDNS and HTTPS certificates.</Step>
        <Step ok={!!ts?.published}>Publish SmartWard to your devices only. In a terminal on this laptop run: <code className="rounded bg-zinc-800 px-1">{ts?.serve_command || 'tailscale serve --bg 127.0.0.1:8000'}</code> <button className="text-xs text-indigo-300 underline" onClick={() => copy(ts?.serve_command || 'tailscale serve --bg 127.0.0.1:8000')}>Copy</button></Step>
        <Step ok={r.has_passphrase && !!r.login}>Choose who may connect and a remote passphrase (below), then turn remote access on.</Step>
      </ol>

      <Field label="Your Tailscale login (only this account may connect)" hint={ts?.login && ts.login !== login ? `Tailscale on this laptop is signed in as ${ts.login}.` : undefined}>
        <div className="flex gap-2"><input className={inputCls} value={login} onChange={e => setLogin(e.target.value)} placeholder="you@example.com" autoCapitalize="none" />
          <Btn onClick={() => save({ login }, 'Saved')} disabled={busy || login.trim() === (r.login || '')}>Save</Btn>{ts?.login && ts.login !== login && <Btn kind="ghost" onClick={() => setLogin(ts.login)}>Use {ts.login}</Btn>}</div></Field>
      <Field label={r.has_passphrase ? 'Remote passphrase (set; type a new one to change it)' : 'Remote passphrase (8+ characters)'} hint="Typed on the phone the first time. It is separate from your app lock PIN.">
        <div className="flex gap-2"><input type="password" autoComplete="new-password" className={inputCls} value={pass} onChange={e => setPass(e.target.value)} />
          <Btn onClick={async () => { await save({ passphrase: pass }, 'Passphrase saved'); setPass(''); }} disabled={busy || pass.length < 8}>Save</Btn></div></Field>

      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={r.enabled} disabled={busy} onChange={e => save({ enabled: e.target.checked }, e.target.checked ? 'Remote access is on' : 'Remote access is off')} />
        <span>Allow my phone to connect<span className="block text-xs text-zinc-500">{r.enabled ? 'On. A phone can read, chat and talk, but cannot change settings, make backups or exports, or erase anything.' : 'Off. Even if Tailscale is publishing SmartWard, the app refuses every connection from outside this laptop.'}</span></span></label>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={r.keep_awake} onChange={e => save({ keep_awake: e.target.checked })} />
        <span>Keep this laptop awake while remote access is on {r.enabled && <Badge tone={r.awake_held ? 'green' : 'amber'}>{r.awake_held ? 'holding' : 'not holding'}</Badge>}<span className="block text-xs text-zinc-500">Stops it from sleeping when idle. Closing the lid still puts it to sleep (that is a system setting SmartWard doesn’t change), and a sleeping laptop can’t be reached.</span></span></label>

      {url && r.enabled && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg bg-zinc-800/60 p-3">
          <canvas ref={qr} width={144} height={144} aria-label="QR code for the phone address" className="rounded bg-white" />
          <div className="min-w-0 text-sm"><div className="mb-1 text-xs text-zinc-500">On your phone (Tailscale connected), scan this or open:</div><div className="break-all font-medium">{url}</div>
            <div className="mt-2 flex gap-2"><Btn small onClick={() => copy(url)}>Copy address</Btn></div>
            <div className="mt-2 text-xs text-zinc-500">Then sign in, and use Share → Add to Home Screen (iPhone) or the menu → Install app (Android).</div></div>
        </div>)}

      {r.sessions.length > 0 && <div><div className="mb-1 flex items-center justify-between text-sm font-medium"><span>Signed-in phones</span><Btn small kind="ghost" onClick={async () => { await post('/remote/revoke', { id: 'all' }); reload(); }}>Sign out all</Btn></div>
        <ul className="space-y-1 text-sm">{r.sessions.map((s: any) => <li key={s.id} className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-1.5"><span className="min-w-0 truncate">{s.agent || 'Unknown device'} <span className="text-xs text-zinc-500">· last used {ago(s.last)}</span></span><Btn small onClick={async () => { await post('/remote/revoke', { id: s.id }); reload(); }}>Sign out</Btn></li>)}</ul></div>}
      {r.log.length > 0 && <details className="text-xs text-zinc-400"><summary className="cursor-pointer">Recent activity</summary><ul className="mt-1 space-y-0.5">{[...r.log].reverse().map((l: any, i: number) => <li key={i}>{new Date(l.ts * 1000).toLocaleString()} — {l.event}{l.detail ? ` (${l.detail})` : ''}</li>)}</ul></details>}
      <div><Btn small onClick={() => { reload(); reloadTs(); }}>Refresh status</Btn></div>
    </Card>
  );
}
