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
