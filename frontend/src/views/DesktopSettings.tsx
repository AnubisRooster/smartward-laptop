import { useEffect, useState } from 'react';
import { errText } from '../api';
import { desktopCall, isDesktop } from '../desktop';
import { Btn, Card, Err } from '../ui';

/** Settings that only exist in SmartWard's own window: start at login, and quitting. */
export default function DesktopSettings() {
  const [login, setLogin] = useState<boolean | null>(null); const [err, setErr] = useState('');
  useEffect(() => { if (isDesktop) desktopCall<boolean>('autostart_enabled').then(setLogin).catch(() => setLogin(null)); }, []);
  if (!isDesktop) return null;
  const toggle = async (on: boolean) => { setErr(''); try { await desktopCall('set_autostart', { enabled: on }); setLogin(on); } catch (e) { setErr(errText(e)); } };
  return (
    <Card className="space-y-3">
      <div id="desktop" className="scroll-mt-16"><h2 className="font-medium">This computer</h2>
        <div className="text-xs text-zinc-500">Closing the window keeps SmartWard running in the tray, so your sources keep refreshing and indexing. Use the tray icon → Quit to stop it.</div></div>
      <Err>{err}</Err>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={!!login} disabled={login === null} onChange={e => toggle(e.target.checked)} />
        <span>Start SmartWard when I log in<span className="block text-xs text-zinc-500">It starts hidden in the tray; open it from there.</span></span></label>
      <Btn small kind="danger" onClick={() => desktopCall('quit_app')}>Quit SmartWard</Btn>
    </Card>
  );
}
