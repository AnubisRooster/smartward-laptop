import { plainForSpeech } from './voiceInput';

/** What "Brief me" says on the Today page: the digest shown there, theme by theme. */
export interface DigestCluster { theme: string; summary?: string; touches_project?: boolean; articles: { title: string }[] }

export function briefParts(clusters: DigestCluster[], maxThemes = 6): string[] {
  if (!clusters.length) return ['There is nothing new on your Today page yet.'];
  const shown = clusters.slice(0, maxThemes);
  const count = clusters.reduce((n, c) => n + c.articles.length, 0);
  const parts = [`Here is your brief: ${count} new article${count === 1 ? '' : 's'} across ${clusters.length} theme${clusters.length === 1 ? '' : 's'}.`];
  shown.forEach((c, i) => {
    parts.push(`${i === 0 ? 'First' : i === shown.length - 1 && shown.length > 1 ? 'Last' : 'Next'}: ${c.theme}${c.touches_project ? ', which touches your projects' : ''}.`);
    parts.push(plainForSpeech(c.summary || '').join(' ') || c.articles.slice(0, 3).map(a => a.title.replace(/[.!?]+$/, '')).join('. ') + '.');
  });
  if (clusters.length > shown.length) parts.push(`And ${clusters.length - shown.length} more theme${clusters.length - shown.length === 1 ? '' : 's'} on the page.`);
  return parts;
}

/** What "Read aloud" says for a weekly memo: the sections in order, each point once, without citations. */
export interface MemoPoint { text: string; project?: string }
export interface MemoLike { week: string; shifted: MemoPoint[]; projects: MemoPoint[]; watch: MemoPoint[]; questions: MemoPoint[]; standing?: { headline: string; verdict: string }[] }

export function memoParts(m: MemoLike): string[] {
  const parts = [`Your strategy memo for week ${m.week.split('-W')[1]?.replace(/^0/, '') || m.week}.`];
  const say = (head: string, pts: MemoPoint[], f = (p: MemoPoint) => p.text) => { if (pts.length) { parts.push(head); pts.forEach(p => parts.push(plainForSpeech(f(p)).join(' '))); } };
  say('What shifted.', m.shifted);
  say('What it may mean for your projects.', m.projects, p => (p.project ? `For ${p.project}: ` : '') + p.text);
  const st = (m.standing || []).filter(s => s.verdict !== 'open');
  if (st.length) { parts.push('How earlier calls are holding up.'); st.forEach(s => parts.push(`${s.headline}: ${s.verdict === 'supported' ? 'supported so far' : 'contradicted so far'}.`)); }
  say('What to watch next week.', m.watch);
  say('Open questions.', m.questions);
  if (parts.length === 1) parts.push('There is nothing in this memo yet.');
  return parts;
}
