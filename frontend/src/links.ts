import { errText, post } from './api';
import { ask, toast } from './feedback';
import { useNav } from './hooks';

/** The first http(s) address in some dropped or pasted text, or null. */
export function firstUrl(text: string | null | undefined): string | null {
  for (const line of (text || '').split(/\r?\n/)) {
    const t = line.trim(); if (!t || t.startsWith('#')) continue;      // text/uri-list allows # comments
    try { const u = new URL(t); if (u.protocol === 'http:' || u.protocol === 'https:') return u.href; } catch { /* not an address */ }
  }
  return null;
}

/** Saves a web page into the library and opens it. */
export async function saveLink(url: string) {
  toast.info('Saving the page…');
  try { const r = await post('/share', { url }); toast.ok('Saved to your library.'); useNav.getState().openArticle(r.id); }
  catch (e) { toast.error(errText(e)); }
}

/** Asks for a link, starting from whatever is on the clipboard when it is one. */
export async function addLinkDialog(initial = '') {
  let start = initial;
  if (!start) { try { start = firstUrl(await navigator.clipboard.readText()) || ''; } catch { /* the webview may not allow reading the clipboard */ } }
  const v = await ask.prompt({ title: 'Save a link', body: 'The page is fetched, added to your library and indexed.', initial: start, label: 'Web address', confirmLabel: 'Save' });
  const url = firstUrl(v);
  if (v && !url) toast.error('That doesn’t look like a web address.');
  else if (url) await saveLink(url);
}
