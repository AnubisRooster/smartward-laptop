import { describe, expect, it } from 'vitest';
import { Endpointer, FRAME } from '../vad';

const frames = (seconds: number, level: number) => Array.from({ length: Math.floor(seconds * 50) }, () => Float32Array.from({ length: FRAME }, () => (Math.random() * 2 - 1) * level));
const run = (ep: Endpointer, frs: Float32Array[]) => frs.map(f => ep.feed(f)).filter(Boolean) as any[];

describe('cutting speech into sentences on the phone', () => {
  it('a room that gets noisier does not hold the microphone open to the limit', () => {
    const ev: any[] = []; const ep = new Endpointer(); let i = 0;
    for (const f of [...frames(2, 0.0003), ...frames(40, 0.01)]) { const e = ep.feed(f); if (e) ev.push({ at: i / 50, ...e }); i++; }
    expect(ev.map(e => e.type)).toEqual(['start', 'end']); expect(ev[1].audio).toBeNull(); expect(ev[1].at).toBeLessThan(6);
  });
  it('still hears you talk over it, and keeps what you said', () => {
    const speech = Array.from({ length: 200 }, (_, k) => Float32Array.from({ length: FRAME }, () => (Math.random() * 2 - 1) * (0.05 + 0.2 * Math.abs(Math.sin(k / 6)))));
    const ev = run(new Endpointer(), [...frames(2, 0.0003), ...speech, ...frames(4, 0.01)]);
    expect(ev.filter(e => e.type === 'end' && e.audio).length).toBe(1);
  });
});
