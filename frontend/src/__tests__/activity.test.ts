import { describe, expect, it } from 'vitest';
import { idleFor, shouldLock, touch } from '../activity';

describe('when the app lock steps in', () => {
  it('not while there has been activity, and never when set to 0', () => {
    expect(shouldLock(0, 15)).toBe(false); expect(shouldLock(14 * 60_000, 15)).toBe(false); expect(shouldLock(16 * 60_000, 15)).toBe(true);
    expect(shouldLock(99 * 60_000, 0)).toBe(false);
  });
  it('touching resets the idle spell', async () => {
    touch(); await new Promise(r => setTimeout(r, 30)); expect(idleFor()).toBeGreaterThanOrEqual(25); touch(); expect(idleFor()).toBeLessThan(25);
  });
  it('the old behaviour, locking after five idle minutes, is gone', () => { expect(shouldLock(6 * 60_000, 15)).toBe(false); });
});
