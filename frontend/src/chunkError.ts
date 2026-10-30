/** True when a page's file couldn't be loaded because the app was rebuilt while this window stayed open (its old file names no longer exist). */
export const isChunkError = (e: unknown): boolean => /dynamically imported module|importing a module script failed|ChunkLoadError|Loading chunk|Failed to fetch dynamically/i.test(String((e as any)?.message ?? e ?? ''));

/** Reload once to pick up the new version; never loop. `now` and `store` are passed in so this can be tested. */
export function reloadOnce(now = Date.now(), store: { getItem(k: string): string | null; setItem(k: string, v: string): void } | null = typeof sessionStorage !== 'undefined' ? sessionStorage : null, reload = () => location.reload()): boolean {
  try {
    const last = Number(store?.getItem('sw.chunkReload') || 0);
    if (now - last < 30000) return false;                      // just did: don't loop
    store?.setItem('sw.chunkReload', String(now));
  } catch { /* storage blocked: still try once */ }
  reload(); return true;
}
