import { useEffect, useMemo, useState } from 'react';
import { errText } from '../api';
import { speech, useLoad } from '../hooks';
import { Badge, Btn, Card, Err, Field, inputCls, Seg } from '../ui';
import { openHelp } from '../HelpGuide';

const GROUPS: Record<string, string> = {
  af: 'American English · female', am: 'American English · male', bf: 'British English · female', bm: 'British English · male',
  ef: 'Spanish · female', em: 'Spanish · male', ff: 'French · female', hf: 'Hindi · female', hm: 'Hindi · male',
  if: 'Italian · female', im: 'Italian · male', jf: 'Japanese · female', jm: 'Japanese · male',
  pf: 'Portuguese · female', pm: 'Portuguese · male', zf: 'Mandarin · female', zm: 'Mandarin · male',
};
const label = (v: string) => { const n = v.slice(3); return n.charAt(0).toUpperCase() + n.slice(1); };
type Profile = { voice: string; rate: number };

const Section = ({ title, children, desc }: { title: string; children: any; desc?: string }) => <Card className="space-y-3"><div id="voice" className="scroll-mt-16"><h2 className="font-medium">{title}</h2>{desc && <div className="text-xs text-zinc-500">{desc}</div>}</div>{children}</Card>;
const Row = ({ children }: { children: any }) => <div className="flex flex-wrap items-center justify-between gap-2 text-sm">{children}</div>;
const selectCls = 'rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-sm';

/** Voices grouped by accent and gender, as <option>s. */
function VoiceOptions({ voices, current }: { voices: string[]; current: string }) {
  const names = voices.includes(current) ? voices : [current, ...voices];
  const groups = new Map<string, string[]>();
  for (const v of names) { const g = GROUPS[v.slice(0, 2)] || 'Other'; groups.set(g, [...(groups.get(g) || []), v]); }
  const order = Object.values(GROUPS);
  return <>{[...groups.entries()].sort((a, b) => (order.indexOf(a[0]) + 1 || 99) - (order.indexOf(b[0]) + 1 || 99)).map(([g, vs]) =>
    <optgroup key={g} label={g}>{vs.map(v => <option key={v} value={v}>{label(v)}</option>)}</optgroup>)}</>;
}

export default function VoiceSettings({ s, save }: { s: any; save: (values: any) => Promise<void> }) {
  const { data: tts } = useLoad<any>('/tts/status', undefined, 5000);
  const { data: mic } = useLoad<any>('/voice/status');
  const [browserVoices, setBrowserVoices] = useState<string[]>([]);
  const [rate, setRate] = useState<number>(Number(s.voice_rate) || 1);
  const [profiles, setProfiles] = useState<Record<string, Profile>>(s.tts_profiles || {});
  const [url, setUrl] = useState<string>(s.tts_url || '');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState('');
  const savedProfiles = JSON.stringify(s.tts_profiles || {});
  useEffect(() => { setProfiles(s.tts_profiles || {}); }, [savedProfiles]);
  useEffect(() => { setRate(Number(s.voice_rate) || 1); }, [s.voice_rate]);
  useEffect(() => {
    if (!speech.browserVoices) return;
    const load = () => setBrowserVoices(speechSynthesis.getVoices().map(v => v.name));
    load(); speechSynthesis.addEventListener('voiceschanged', load);
    return () => speechSynthesis.removeEventListener('voiceschanged', load);
  }, []);

  const up = !!tts?.up; const voices: string[] = tts?.voices || [];
  const engine: string = s.tts_engine || 'auto';
  const natural = engine === 'kokoro' || (engine === 'auto' && up);
  const dirty = JSON.stringify(profiles) !== savedProfiles;
  const names = useMemo(() => Object.keys(profiles), [profiles]);

  const listen = async (voice: string, speed: number, kokoro = natural) => {
    setErr(''); setBusy(voice + speed);
    try { const m = await speech.sample(kokoro ? 'kokoro' : 'browser', voice, speed); if (m) setErr(m); }
    catch (e) { setErr(errText(e)); }
    setBusy('');
  };
  const saveProfiles = async () => { setErr(''); try { await save({ tts_profiles: profiles }); } catch (e) { setErr(errText(e)); } };
  const addProfile = () => { let n = names.length + 1; while (`Profile ${n}` in profiles) n++; setProfiles({ ...profiles, [`Profile ${n}`]: { voice: s.tts_voice || 'af_heart', rate } }); };
  const rename = (from: string, to: string) => {
    const next = to.trim().slice(0, 40); if (!next || next === from || next in profiles) return;
    setProfiles(Object.fromEntries(Object.entries(profiles).map(([k, v]) => [k === from ? next : k, v])));
  };
  const edit = (name: string, patch: Partial<Profile>) => setProfiles({ ...profiles, [name]: { ...profiles[name], ...patch } });
  const remove = (name: string) => { const { [name]: _, ...rest } = profiles; setProfiles(rest); };

  return (
    <Section title="Voice" desc="Read-aloud runs on this computer, so article text never leaves it. The natural voice sounds far less robotic than the browser’s built-in one.">
      <Err>{err}</Err>
      <Row><span>Speech input (hands-free chat)</span>{mic?.installed ? <Badge tone="green">Installed · {mic.model}</Badge> : <Badge tone="amber">Not installed</Badge>}</Row>
      {mic && !mic.installed && <div className="text-xs text-zinc-500">Hands-free chat needs a local speech model (about 500 MB, downloaded once). <button className="text-indigo-300 underline" onClick={() => openHelp('voice-reading-aloud-and-talking')}>Step-by-step guide</button>. Run <code>~/SmartWardApp/stt/setup.sh</code>, then use the 🎙 button in Chat. The microphone is open only while hands-free is on, and nothing is sent anywhere.</div>}
      <Row><span>Voice</span><Seg value={engine} onChange={x => save({ tts_engine: x })} options={[['auto', 'Automatic'], ['kokoro', 'Natural'], ['browser', 'Browser']]} /></Row>
      <Row><span>Natural voice</span>{up ? <Badge tone="green">Running · {voices.length} voices</Badge> : <Badge tone="red">Not running</Badge>}</Row>
      {!up && engine !== 'browser' && <div className="text-xs text-zinc-500">Start SmartWard from its menu icon (or run <code>~/SmartWardApp/bin/start_smartward.sh</code>) to start it. Until then the browser voice reads.</div>}

      <Field label={natural ? 'Reading voice' : 'Reading voice (browser)'}>
        <div className="flex gap-2">
          {natural
            ? <select className={inputCls} value={s.tts_voice || 'af_heart'} onChange={e => save({ tts_voice: e.target.value })}><VoiceOptions voices={voices} current={s.tts_voice || 'af_heart'} /></select>
            : <select className={inputCls} value={s.voice_name || ''} onChange={e => save({ voice_name: e.target.value })}><option value="">System default</option>{browserVoices.map(v => <option key={v} value={v}>{v}</option>)}</select>}
          <Btn onClick={() => listen(natural ? (s.tts_voice || 'af_heart') : (s.voice_name || ''), rate)} disabled={!!busy}>{busy ? '…' : '▶'} Listen</Btn>
        </div>
      </Field>
      <Row><span>Speaking rate {rate.toFixed(2)}×</span>
        <input type="range" min="0.5" max="2" step="0.05" value={rate} onChange={e => setRate(Number(e.target.value))}
          onMouseUp={() => save({ voice_rate: rate })} onKeyUp={() => save({ voice_rate: rate })} onTouchEnd={() => save({ voice_rate: rate })} /></Row>

      <div className="space-y-2 border-t border-zinc-800 pt-3">
        <div><h3 className="text-sm font-medium">Reading profiles</h3>
          <div className="text-xs text-zinc-500">A profile is a voice and a speed you can switch between, like a calm evening reader and a quick one for the commute. The one in use replaces the voice and rate above.</div></div>
        {names.length === 0 && <div className="text-xs text-zinc-500">No profiles yet.</div>}
        {names.map(name => { const p = profiles[name]; return (
          <div key={name} className="space-y-2 rounded-lg border border-zinc-800 p-3">
            <div className="flex gap-2"><input className={inputCls} defaultValue={name} key={name} maxLength={40} aria-label="Profile name" onBlur={e => { rename(name, e.target.value); e.target.value = e.target.value.trim() || name; }} onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }} />
              <Btn kind="danger" small onClick={() => remove(name)}>Delete</Btn></div>
            <div className="flex flex-wrap items-center gap-2">
              <select className={selectCls} aria-label="Profile voice" value={p.voice} onChange={e => edit(name, { voice: e.target.value })}><VoiceOptions voices={voices} current={p.voice} /></select>
              <input type="range" min="0.5" max="2" step="0.05" aria-label="Profile speed" value={p.rate} onChange={e => edit(name, { rate: Number(e.target.value) })} /><span className="w-12 text-xs text-zinc-400">{p.rate.toFixed(2)}×</span>
              <Btn small onClick={() => listen(p.voice, p.rate, true)} disabled={!up || !!busy}>▶ Listen</Btn></div>
          </div>); })}
        <div className="flex flex-wrap items-center gap-2">
          <Btn small onClick={addProfile} disabled={!up || names.length >= 24}>Add a profile</Btn>
          <Btn small kind="primary" onClick={saveProfiles} disabled={!dirty}>Save profiles</Btn>
          {dirty && <span className="text-xs text-amber-500">Unsaved changes</span>}
        </div>
        <Row><span>Profile in use</span>
          <select className={selectCls} value={s.tts_profile || ''} disabled={dirty} onChange={e => save({ tts_profile: e.target.value })}>
            <option value="">None — use the voice above</option>{Object.keys(s.tts_profiles || {}).map(n => <option key={n} value={n}>{n}</option>)}</select></Row>
      </div>

      <details className="text-xs text-zinc-400"><summary className="cursor-pointer">Speech server</summary>
        <Field label="Address (must be on this computer)"><div className="mt-1 flex gap-2"><input className={inputCls} value={url} onChange={e => setUrl(e.target.value)} spellCheck={false} /><Btn onClick={async () => { setErr(''); try { await save({ tts_url: url.trim() }); } catch (e) { setErr(errText(e)); } }}>Use</Btn></div></Field>
      </details>
    </Section>
  );
}
