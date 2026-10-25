/** Is anyone using Selfward? The app lock watches this, so it never locks under you while you read, scroll, talk or wait for an answer. */
let last = Date.now();

/** Call whenever something is going on that counts as use (a keypress, a hands-free turn, an answer being written). */
export const touch = () => { last = Date.now(); };
export const idleFor = () => Date.now() - last;

/** True when the idle spell is long enough to lock. `idleMinutes` of 0 means never lock for inactivity. */
export const shouldLock = (idleMs: number, idleMinutes: number) => idleMinutes > 0 && idleMs > idleMinutes * 60_000;

const EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart', 'scroll', 'focus'] as const;
/** Starts counting your own activity in the window. Returns a function that stops. */
export function watchActivity(): () => void {
  touch(); EVENTS.forEach(e => window.addEventListener(e, touch, { capture: true, passive: true }));
  return () => EVENTS.forEach(e => window.removeEventListener(e, touch, true));
}
