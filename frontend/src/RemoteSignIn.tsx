import { useState } from 'react';
import { errText, post } from './api';
import { readPref, setPref, ThemePref } from './theme';
import { Seg } from './ui';
import { Btn, Err, inputCls } from './ui';

/** Shown on a phone (or any device reaching SmartWard through the private network) that hasn't signed in yet. */
export default function RemoteSignIn({ onDone }: { onDone: () => void }) {
  const [pass, setPass] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); setErr(''); try { await post('/remote/login', { passphrase: pass }); onDone(); } catch (e) { setErr(errText(e)); setPass(''); } setBusy(false); };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950 p-6" style={{ paddingTop: 'env(safe-area-inset-top)', paddingBottom: 'env(safe-area-inset-bottom)' }}>
      <form onSubmit={e => { e.preventDefault(); go(); }} className="w-full max-w-sm space-y-3 text-center">
        <img src="/favicon.svg" alt="" className="mx-auto h-16 w-16" />
        <h1 className="text-lg font-semibold">Sign in to SmartWard</h1>
        <p className="text-sm text-zinc-500">This is your laptop’s SmartWard, reached over your private network. Use the remote passphrase you set in Settings → Remote.</p>
        <input autoFocus type="password" autoComplete="current-password" value={pass} onChange={e => setPass(e.target.value)} placeholder="Remote passphrase" aria-label="Remote passphrase" className={inputCls + ' text-center'} />
        <Err>{err}</Err>
        <Btn type="submit" kind="primary" disabled={!pass} loading={busy}>Sign in</Btn>
      </form>
    </div>
  );
}

/** What "Settings" is on a phone: settings are changed on the laptop; here you sign out and pick light or dark. */
export function PhoneAccount({ embedded = false }: { embedded?: boolean }) {
  const [theme, setTheme] = useState<ThemePref>(readPref());
  return (
    <div className={embedded ? '' : 'h-full overflow-y-auto'}><div className="mx-auto max-w-2xl space-y-4 p-5">
      <h1 className="text-lg font-semibold">This phone</h1>
      <div className="flex items-center justify-between text-sm"><span>Theme</span><Seg value={theme} onChange={(x: string) => { setTheme(x as ThemePref); setPref(x as ThemePref); }} options={[['system', 'System'], ['light', 'Light'], ['dark', 'Dark']]} /></div>
      <p className="text-sm text-zinc-500">Keys, the app lock, GitHub links, backups and exports are only available on the laptop itself, so nothing here can copy your library or send it elsewhere.</p>
      <Btn kind="danger" onClick={async () => { try { await post('/remote/logout'); } catch { /* already signed out */ } location.reload(); }}>Sign out of this phone</Btn>
    </div></div>
  );
}
