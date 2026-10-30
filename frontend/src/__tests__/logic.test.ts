import { describe, expect, it } from 'vitest';
import { hashFor, parseHash, HOME } from '../nav';
import { resolveTheme } from '../theme';
import { step, tabForKey, isTyping } from '../shortcuts';
import { chunkForSpeech, sameData } from '../hooks';

describe('address <-> place', () => {
  it('round-trips every kind of place', () => {
    for (const p of [
      { ...HOME, tab: 'reading' as const, articleId: 12 }, { ...HOME, tab: 'reading' as const, sources: true },
      { ...HOME, tab: 'graph' as const, themeId: 3 }, { ...HOME, tab: 'chat' as const, convId: 7 },
      { ...HOME, tab: 'projects' as const, projectId: 2 }, { ...HOME, tab: 'settings' as const }, HOME,
    ]) expect(parseHash(hashFor(p))).toEqual(p);
  });
  it('rejects addresses that are not ours', () => {
    for (const h of ['', '#', '#/nope', '#/reading/abc', '#/graph/1/2', '#/chat/sources']) expect(parseHash(h)).toBeNull();
  });
});

describe('theme', () => {
  it('an explicit choice wins, "system" follows the OS', () => {
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
    expect(resolveTheme('garbage', true)).toBe('dark');
    expect(resolveTheme(null, false)).toBe('light');
  });
});

describe('shortcuts', () => {
  it('maps number keys to tabs', () => {
    expect(tabForKey('1')).toBe('today'); expect(tabForKey('3')).toBe('radar'); expect(tabForKey('6')).toBe('projects'); expect(tabForKey(',')).toBe('settings');
    expect(tabForKey('7')).toBeNull(); expect(tabForKey('a')).toBeNull();
  });
  it('stays out of the way while typing', () => {
    expect(isTyping({ tagName: 'INPUT' })).toBe(true); expect(isTyping({ tagName: 'TEXTAREA' })).toBe(true);
    expect(isTyping({ tagName: 'DIV', isContentEditable: true })).toBe(true); expect(isTyping({ tagName: 'BUTTON' })).toBe(false); expect(isTyping(null)).toBe(false);
  });
  it('steps through a list and stops at the ends', () => {
    const ids = [5, 6, 7];
    expect(step(ids, null, 1)).toBe(5); expect(step(ids, null, -1)).toBe(7);
    expect(step(ids, 5, 1)).toBe(6); expect(step(ids, 7, 1)).toBe(7); expect(step(ids, 5, -1)).toBe(5);
    expect(step(ids, 99, 1)).toBe(5); expect(step([], 1, 1)).toBeNull();
  });
});

describe('polling', () => {
  it('treats equal payloads as unchanged', () => {
    expect(sameData({ a: [1, 2] }, { a: [1, 2] })).toBe(true); expect(sameData({ a: 1 }, { a: 2 })).toBe(false); expect(sameData(null, null)).toBe(true);
  });
});

describe('speech chunks', () => {
  it('never exceeds the limit and keeps all the words', () => {
    const text = Array.from({ length: 80 }, (_, i) => `Sentence number ${i} is here.`).join(' ');
    const parts = chunkForSpeech(text, 200);
    expect(parts.every(p => p.length <= 200)).toBe(true);
    expect(parts.join(' ').replace(/\s+/g, ' ')).toBe(text);
  });
});

import { firstUrl } from '../links';
describe('links', () => {
  it('finds the first web address in dropped text', () => {
    expect(firstUrl('https://example.com/a')).toBe('https://example.com/a');
    expect(firstUrl('# a comment\r\nhttps://example.com/b\r\nhttps://other.org')).toBe('https://example.com/b');
    expect(firstUrl('  http://localhost:8000/x  ')).toBe('http://localhost:8000/x');
  });
  it('ignores anything that is not http(s)', () => {
    for (const t of ['', null, undefined, 'hello', 'javascript:alert(1)', 'file:///etc/passwd', 'ftp://x.org']) expect(firstUrl(t as any)).toBeNull();
  });
});

import { parseVoice, plainForSpeech } from '../voiceInput';
describe('hands-free phrases', () => {
  it('turns hands-free off and stops talking', () => {
    for (const t of ['Stop listening.', 'stop listening', 'SmartWard, stop listening', 'Goodbye!']) expect(parseVoice(t, { pending: false }).kind).toBe('stop-listening');
    for (const t of ['Stop.', 'be quiet', 'Never mind.']) expect(parseVoice(t, { pending: false }).kind).toBe('stop');
  });
  it('yes and no only answer an approval that is waiting', () => {
    expect(parseVoice('Yes.', { pending: true }).kind).toBe('approve'); expect(parseVoice('go ahead', { pending: true }).kind).toBe('approve');
    expect(parseVoice('No', { pending: true }).kind).toBe('decline'); expect(parseVoice('cancel', { pending: true }).kind).toBe('decline');
    expect(parseVoice('Yes.', { pending: false })).toEqual({ kind: 'text', text: 'Yes.' });
  });
  it('anything else goes to the strategist as written', () => {
    expect(parseVoice('  What changed in vLLM 0.9? ', { pending: false })).toEqual({ kind: 'text', text: 'What changed in vLLM 0.9?' });
    expect(parseVoice('stop the benchmark run and summarise', { pending: false }).kind).toBe('text');
  });
});
describe('answers read aloud', () => {
  it('drops marks, citations and code', () => {
    const parts = plainForSpeech('## Ideas\n\n1. **Quality** vs diversity [R1]\n2. See [the paper](https://x.org/a)\n\n```py\nprint(1)\n```\n> quoted `inline`');
    expect(parts).toEqual(['Ideas', 'Quality vs diversity', 'See the paper', '(code omitted)', 'quoted inline']);
    expect(parts.join(' ')).not.toMatch(/[*#`\[\]]|https/);
  });
  it('handles empty input', () => { expect(plainForSpeech('')).toEqual([]); });
});

import { wantAudioChat, takeAudioChat } from '../voiceIntent';
describe('audio chat on open', () => {
  it('is handed over once', () => { expect(takeAudioChat()).toBe(false); wantAudioChat(); expect(takeAudioChat()).toBe(true); expect(takeAudioChat()).toBe(false); });
});

import { briefParts } from '../digestBrief';
describe('Today brief', () => {
  const c = (theme: string, titles: string[], extra: any = {}) => ({ theme, articles: titles.map(title => ({ title })), ...extra });
  it('says what is on the page, theme by theme', () => {
    const p = briefParts([c('KV cache', ['A.', 'B'], { touches_project: true, summary: 'Eviction policies matter.' }), c('Speculative decoding', ['C', 'D', 'E', 'F'])]);
    expect(p[0]).toBe('Here is your brief: 6 new articles across 2 themes.');
    expect(p).toContain('First: KV cache, which touches your projects.'); expect(p).toContain('Eviction policies matter.');
    expect(p).toContain('Last: Speculative decoding.'); expect(p).toContain('C. D. E.');
  });
  it('is honest when there is nothing', () => { expect(briefParts([])).toEqual(['There is nothing new on your Today page yet.']); });
  it('does not read a hundred themes', () => {
    const p = briefParts(Array.from({ length: 10 }, (_, i) => c('T' + i, ['x']))); expect(p.length).toBe(1 + 6 * 2 + 1); expect(p[p.length - 1]).toBe('And 4 more themes on the page.');
  });
});

import { Endpointer, FRAME } from '../vad';
import { encodeWav, toRate16k } from '../wav';
const gauss = () => { let u = 0, v = 0; while (!u) u = Math.random(); while (!v) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
const frames = (secs: number, level: number) => Array.from({ length: Math.round(secs * 50) }, () => Float32Array.from({ length: FRAME }, () => gauss() * level / 32768));
const run = (ep: Endpointer, fr: Float32Array[]) => fr.map(f => ep.feed(f)).filter(Boolean) as any[];
describe('phone voice: sentence detection (same behaviour as the laptop listener)', () => {
  it('a sentence between silences is one utterance with its trailing silence', () => {
    const ev = run(new Endpointer(), [...frames(2, 8), ...frames(1.5, 3000), ...frames(2, 8)]);
    expect(ev.map(e => e.type)).toEqual(['start', 'end']); const secs = ev[1].audio.length / 16000; expect(secs).toBeGreaterThan(1.5); expect(secs).toBeLessThan(2.8);
  });
  it('silence and steady room noise never start', () => { expect(run(new Endpointer(), frames(10, 8))).toEqual([]); expect(run(new Endpointer(), frames(10, 40))).toEqual([]); });
  it('a click is dropped', () => { const ev = run(new Endpointer(), [...frames(2, 8), ...frames(0.1, 3000), ...frames(2, 8)]); expect(ev.filter(e => e.type === 'end').every(e => e.audio === null)).toBe(true); });
  it('a short pause inside a sentence does not split it', () => { expect(run(new Endpointer(), [...frames(2, 8), ...frames(1, 3000), ...frames(0.4, 8), ...frames(1, 3000), ...frames(2, 8)]).map(e => e.type)).toEqual(['start', 'end']); });
  it('two sentences are two utterances', () => { expect(run(new Endpointer(), [...frames(2, 8), ...frames(1, 3000), ...frames(1.5, 8), ...frames(1, 3000), ...frames(1.5, 8)]).map(e => e.type)).toEqual(['start', 'end', 'start', 'end']); });
  it('adapts to a noisy room', () => { expect(run(new Endpointer(), [...frames(3, 150), ...frames(1.5, 4000), ...frames(2, 150)]).map(e => e.type)).toEqual(['start', 'end']); });
});
describe('phone voice: audio encoding', () => {
  it('writes a valid 16 kHz mono WAV', async () => {
    const blob = encodeWav(Float32Array.from([0, 0.5, -0.5, 1, -1, 2]), 16000); const b = new DataView(await blob.arrayBuffer());
    expect(blob.type).toBe('audio/wav'); expect(blob.size).toBe(44 + 12);
    expect(String.fromCharCode(b.getUint8(0), b.getUint8(1), b.getUint8(2), b.getUint8(3))).toBe('RIFF'); expect(b.getUint32(24, true)).toBe(16000); expect(b.getUint16(22, true)).toBe(1);
    expect(b.getInt16(46, true)).toBeGreaterThan(16000); expect(b.getInt16(50, true)).toBe(32767); expect(b.getInt16(52, true)).toBe(-32768); expect(b.getInt16(54, true)).toBe(32767);   // 1, -1 and an out-of-range 2: clipped, not wrapped
  });
  it('down-samples 48 kHz to 16 kHz without losing track of the remainder', () => {
    const carry = { pos: 0 }; const a = toRate16k(new Float32Array(4096).fill(0.25), 48000, carry); const b = toRate16k(new Float32Array(4096).fill(0.25), 48000, carry);
    expect(a.length + b.length).toBeGreaterThanOrEqual(2730); expect(a.length + b.length).toBeLessThanOrEqual(2731); expect(a.every(x => Math.abs(x - 0.25) < 1e-6)).toBe(true);
    expect(toRate16k(new Float32Array(10), 16000).length).toBe(10);
  });
});

import { qrDataUrl } from '../qr';
describe('phone address QR', () => {
  it('makes a PNG picture of the address, and a different one for a different address', async () => {
    const a = await qrDataUrl('https://laptop.tail1234.ts.net'); const b = await qrDataUrl('https://other.tail1234.ts.net');
    expect(a.startsWith('data:image/png;base64,')).toBe(true); expect(a.length).toBeGreaterThan(300); expect(a).not.toBe(b);
  });
});

import { apiBase } from '../api';
describe('where the page finds the API', () => {
  it('uses its own address on the laptop window and on a phone (never the phone\'s own localhost)', () => {
    expect(apiBase({ protocol: 'http:', port: '8000' })).toBe('');
    expect(apiBase({ protocol: 'https:', port: '' })).toBe('');            // a phone, through the private https address
    expect(apiBase({ protocol: 'https:', port: '8443' })).toBe('');
  });
  it('points the dev server and the splash page at the laptop API', () => {
    expect(apiBase({ protocol: 'http:', port: '1420' })).toBe('http://localhost:8000');
    expect(apiBase({ protocol: 'tauri:', port: '' })).toBe('http://localhost:8000');
  });
});

describe('answers read aloud: tables, rules and dashes', () => {
  const said = (md: string) => plainForSpeech(md).join(' | ');
  it('reads a table as rows, not as bars and dashes', () => {
    const t = '| Method | Speedup | Cost |\n|---|:---:|---:|\n| EAGLE | 2.1x | low |\n| Medusa | 1.8x | medium |';
    expect(plainForSpeech(t)).toEqual(['Method, Speedup, Cost.', 'EAGLE, 2.1x, low.', 'Medusa, 1.8x, medium.']);
  });
  it('reads a table without outer bars too', () => { expect(plainForSpeech('Name | Size\n--- | ---\nsmall | 3B')).toEqual(['Name, Size.', 'small, 3B.']); });
  it('drops horizontal rules entirely', () => { expect(plainForSpeech('First point.\n\n---\n\nSecond point.\n***\n- - -\n___')).toEqual(['First point.', 'Second point.']); });
  it('turns dashes used as pauses into pauses and keeps hyphens inside words', () => {
    expect(said('Speculative decoding — when it helps – and when it doesn’t -- is subtle.')).toBe('Speculative decoding, when it helps, and when it doesn’t, is subtle.');
    expect(said('Memory - the main limit - matters for trade-offs and 2-3x gains.')).toBe('Memory, the main limit, matters for trade-offs and 2-3x gains.');
  });
  it('says arrows as "to" and links as "a link", and drops stray bars and maths dollars', () => {
    expect(said('Prefill -> decode, see https://arxiv.org/abs/2610.31667v1 for pass@$k$ | notes')).toBe('Prefill to decode, see a link for pass@k, notes.');
  });
  it('speaks a bulleted list of dash-led lines without the dashes', () => { expect(plainForSpeech('- first\n- second\n+ third')).toEqual(['first', 'second', 'third']); });
  it('leaves nothing but marks as nothing', () => { expect(plainForSpeech('| | |\n|---|---|\n---')).toEqual([]); });
  it('a typical model answer comes out clean', () => {
    const md = '## Key ideas\n\n**1. Pruning** — keeps *diverse* candidates [R1].\n\n| Setting | Result |\n|---|---|\n| small k | worse |\n\n---\n\nSee [the paper](https://x.org/p) -> section 3.';
    const out = plainForSpeech(md).join(' ');
    expect(out).not.toMatch(/[|*#\[\]`]|--|—|https|R1/); expect(out).toContain('Pruning, keeps diverse candidates.'); expect(out).toContain('small k, worse.'); expect(out).toContain('See the paper to section 3.');
  });
});


import { isChunkError, reloadOnce } from '../chunkError';
describe('an old window after an update', () => {
  it('recognises a page file that no longer exists, in each browser\'s words', () => {
    for (const m of ['Failed to fetch dynamically imported module: http://127.0.0.1:8000/assets/Settings-abc.js', 'error loading dynamically imported module', 'Importing a module script failed.', 'ChunkLoadError: Loading chunk 7 failed']) expect(isChunkError(new Error(m))).toBe(true);
    for (const m of ['x is not a function', 'Network Error', '']) expect(isChunkError(new Error(m))).toBe(false); expect(isChunkError(null)).toBe(false);
  });
  it('reloads once, then not again for 30 seconds, so it can never loop', () => {
    const mem: Record<string, string> = {}; const store = { getItem: (k: string) => mem[k] ?? null, setItem: (k: string, v: string) => { mem[k] = v; } }; let reloads = 0; const go = () => { reloads++; };
    expect(reloadOnce(1_000_000, store, go)).toBe(true); expect(reloadOnce(1_010_000, store, go)).toBe(false); expect(reloads).toBe(1);
    expect(reloadOnce(1_031_000, store, go)).toBe(true); expect(reloads).toBe(2);
  });
});
