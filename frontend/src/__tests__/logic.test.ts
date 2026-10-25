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
    expect(tabForKey('1')).toBe('today'); expect(tabForKey('5')).toBe('projects'); expect(tabForKey(',')).toBe('settings');
    expect(tabForKey('6')).toBeNull(); expect(tabForKey('a')).toBeNull();
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
