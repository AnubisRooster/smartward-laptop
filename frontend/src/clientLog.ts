import { BASE } from './api';

/** Tell the local API when the page breaks, so a problem in a window nobody can look into can still be diagnosed. Never throws. */
export function reportError(where: string, error: unknown) {
  try {
    const e = error as any;
    void fetch(BASE + '/api/clientlog', { method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
      body: JSON.stringify({ where, page: location.hash, message: e?.message ?? String(error), stack: String(e?.stack ?? '').split('\n').slice(0, 4).join(' / '), agent: navigator.userAgent.slice(-80) }) }).catch(() => {});
  } catch { /* reporting must never cause a problem of its own */ }
}

export function watchErrors() {
  window.addEventListener('error', e => reportError('error', e.error ?? e.message));
  window.addEventListener('unhandledrejection', e => reportError('promise', e.reason));
}
