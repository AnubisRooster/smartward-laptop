import { Tab } from './nav';

/** Everything the keyboard can do, in one place: the handlers read it and the help overlay (?) shows it. */
export const SHORTCUTS: { keys: string; does: string; where: string }[] = [
  { keys: 'Ctrl K', does: 'Search everything and run commands', where: 'Anywhere' },
  { keys: '1 – 5', does: 'Today, Reading, Graph, Chat, Projects', where: 'Anywhere' },
  { keys: ',', does: 'Settings', where: 'Anywhere' },
  { keys: '/', does: 'Search articles', where: 'Anywhere' },
  { keys: '?', does: 'Show this list', where: 'Anywhere' },
  { keys: 'j / k', does: 'Next / previous article', where: 'Reading' },
  { keys: 's', does: 'Star or unstar the open article', where: 'Reading' },
  { keys: 'u', does: 'Mark the open article unread', where: 'Reading' },
  { keys: 'Esc', does: 'Close a dialog', where: 'Anywhere' },
  { keys: 'Enter', does: 'Send a message (Shift+Enter for a new line)', where: 'Chat' },
];

const NUMBER_TABS: Tab[] = ['today', 'reading', 'graph', 'chat', 'projects'];
export const tabForKey = (key: string): Tab | null => key === ',' ? 'settings' : /^[1-5]$/.test(key) ? NUMBER_TABS[Number(key) - 1] : null;

/** True while the user is typing somewhere, when single-key shortcuts must stay out of the way. */
export function isTyping(el: { tagName?: string; isContentEditable?: boolean } | null): boolean {
  if (!el) return false;
  const t = (el.tagName || '').toLowerCase();
  return t === 'input' || t === 'textarea' || t === 'select' || !!el.isContentEditable;
}

/** The id after (or before) `current` in `ids`; the first one when nothing is open; the same one at either end. */
export function step(ids: number[], current: number | null, dir: 1 | -1): number | null {
  if (!ids.length) return null;
  const i = current == null ? -1 : ids.indexOf(current);
  if (i < 0) return dir === 1 ? ids[0] : ids[ids.length - 1];
  return ids[Math.max(0, Math.min(ids.length - 1, i + dir))];
}
