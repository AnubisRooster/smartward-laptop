/** Where you are in the app, and how that is written in the address (`#/reading/12`) so Back, Forward and Reload work. */
export type Tab = 'today' | 'reading' | 'radar' | 'graph' | 'chat' | 'projects' | 'settings';
export const TABS: Tab[] = ['today', 'reading', 'radar', 'graph', 'chat', 'projects', 'settings'];

export interface Place { tab: Tab; articleId: number | null; projectId: number | null; convId: number | null; themeId: number | null; sources: boolean }
export const HOME: Place = { tab: 'today', articleId: null, projectId: null, convId: null, themeId: null, sources: false };

export function hashFor(p: Place): string {
  const id = (n: number | null) => (n == null ? '' : `/${n}`);
  switch (p.tab) {
    case 'reading': return p.sources ? '#/reading/sources' : `#/reading${id(p.articleId)}`;
    case 'graph': return `#/graph${id(p.themeId)}`;
    case 'chat': return `#/chat${id(p.convId)}`;
    case 'projects': return `#/projects${id(p.projectId)}`;
    default: return `#/${p.tab}`;
  }
}

/** The place an address stands for, or null when it isn't one of ours. */
export function parseHash(hash: string): Place | null {
  const m = /^#\/([a-z]+)(?:\/([A-Za-z0-9]+))?$/.exec(hash || '');
  if (!m || !(TABS as string[]).includes(m[1])) return null;
  const tab = m[1] as Tab; const arg = m[2];
  const n = arg !== undefined && /^\d+$/.test(arg) ? Number(arg) : null;
  if (arg !== undefined && n === null && !(tab === 'reading' && arg === 'sources')) return null;
  const place: Place = { ...HOME, tab };
  if (tab === 'reading') { if (arg === 'sources') place.sources = true; else place.articleId = n; }
  if (tab === 'graph') place.themeId = n;
  if (tab === 'chat') place.convId = n;
  if (tab === 'projects') place.projectId = n;
  return place;
}
