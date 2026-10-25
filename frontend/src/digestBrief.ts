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
