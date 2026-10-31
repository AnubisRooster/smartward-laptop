import { useEffect, useState } from 'react';
import { ago, del, errText } from '../api';
import { currentSub, disablePush, enablePush, needsHomeScreen, pushSupported, testPush } from '../pushClient';
import { useLoad } from '../hooks';
import { toast } from '../feedback';
import { Btn } from '../ui';

/** On a phone: turn notifications on or off for this device, and send a test. */
export function PhonePush() {
  const [sub, setSub] = useState<PushSubscription | null>(null); const [busy, setBusy] = useState(false);
  useEffect(() => { currentSub().then(setSub).catch(() => {}); }, []);
  const run = async (fn: () => Promise<any>) => { setBusy(true); try { await fn(); } catch (e) { toast.error(e instanceof Error && !('response' in e) ? e.message : errText(e)); } setBusy(false); };
  if (needsHomeScreen()) return <p className="text-sm text-zinc-400">On iPhone, notifications only work from the Home Screen app: tap Share, then “Add to Home Screen”, open SmartWard from there and come back here.</p>;
  if (!pushSupported()) return <p className="text-sm text-zinc-400">This browser can’t receive notifications. Try Chrome on Android, or Safari from the Home Screen on iPhone.</p>;
  return (
    <div className="space-y-2 text-sm">
      <p className="text-xs text-zinc-500">Watch matches and the weekly memo, even when SmartWard is closed. The notification only says something new is waiting; details show when you open it. At most a few a day.</p>
      <div className="flex flex-wrap gap-2">{sub
        ? <><Btn onClick={() => run(async () => { await testPush(sub); toast.ok('Sent. It should arrive in a few seconds.'); })} loading={busy}>Send a test</Btn><Btn kind="ghost" onClick={() => run(async () => { await disablePush(); setSub(null); })}>Turn off on this phone</Btn></>
        : <Btn kind="primary" onClick={() => run(async () => { setSub(await enablePush()); toast.ok('Notifications are on for this phone'); })} loading={busy}>Turn on for this phone</Btn>}</div>
    </div>
  );
}

/** On the laptop: which phones get notifications, and a way to forget one. */
export function PushDevices() {
  const { data, reload, error } = useLoad<any>('/push/key');
  const devices: any[] = data?.devices || [];
  if (error) return <p className="text-xs text-zinc-500">{error}</p>;
  return (
    <div className="space-y-1 text-sm">
      <div className="text-xs text-zinc-500">Phones: turn notifications on from SmartWard on the phone (Settings → Notifications). {devices.length ? '' : 'None yet.'}</div>
      {devices.map(d => <div key={d.id} className="flex items-center gap-2"><span>{d.label || 'Device'}</span><span className="text-xs text-zinc-500">added {ago(d.created)}{d.last_ok ? ` · last delivered ${ago(d.last_ok)}` : ''}{d.fails ? ` · ${d.fails} failed` : ''}</span>
        <Btn small kind="ghost" onClick={async () => { await del(`/push/devices/${d.id}`); reload(); }}>Forget</Btn></div>)}
    </div>
  );
}
