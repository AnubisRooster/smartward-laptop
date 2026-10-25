export type ThemePref = 'system' | 'light' | 'dark';
export const THEME_KEY = 'sw.theme';

/** What actually shows: an explicit choice wins; "system" follows the operating system. */
export const resolveTheme = (pref: ThemePref | string | null | undefined, systemDark: boolean): 'light' | 'dark' =>
  pref === 'light' ? 'light' : pref === 'dark' ? 'dark' : systemDark ? 'dark' : 'light';

export function readPref(): ThemePref {
  try { const v = localStorage.getItem(THEME_KEY); if (v === 'light' || v === 'dark' || v === 'system') return v; } catch { /* storage can be blocked */ }
  return 'system';
}

export function applyTheme(pref: ThemePref) {
  const dark = typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches;
  const t = resolveTheme(pref, dark);
  document.documentElement.dataset.theme = t;
  document.documentElement.style.colorScheme = t;
  window.dispatchEvent(new Event('sw-theme'));
}

export function setPref(pref: ThemePref) {
  try { localStorage.setItem(THEME_KEY, pref); } catch { /* ignore */ }
  applyTheme(pref);
}

/** Apply the saved choice now and keep following the system while it is "system". */
export function initTheme() {
  applyTheme(readPref());
  if (typeof matchMedia === 'function') matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (readPref() === 'system') applyTheme('system'); });
}

export const isLight = () => document.documentElement.dataset.theme === 'light';
