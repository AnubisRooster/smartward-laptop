/** What a spoken phrase means in a hands-free chat. Pure, so it can be tested without a microphone. */

export type VoiceCmd =
  | { kind: 'stop-listening' } | { kind: 'stop' } | { kind: 'approve' } | { kind: 'decline' }
  | { kind: 'text'; text: string };

const norm = (t: string) => t.toLowerCase().replace(/[^a-z' ]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/^(hey |ok |okay )?smartward,? ?/, '');
const STOP_LISTENING = new Set(['stop listening', 'turn off hands free', 'hands free off', 'stop hands free', 'goodbye', 'that is all', 'that\'s all', 'end hands free']);
const STOP = new Set(['stop', 'stop talking', 'stop reading', 'be quiet', 'quiet', 'shut up', 'never mind', 'nevermind', 'cancel', 'enough']);
const APPROVE = new Set(['yes', 'yeah', 'yep', 'approve', 'approved', 'go ahead', 'do it', 'okay', 'ok', 'sure', 'allow', 'yes please', 'approve it']);
const DECLINE = new Set(['no', 'nope', 'decline', 'deny', 'reject', 'don\'t', 'do not', 'no thanks', 'cancel', 'never mind', 'nevermind', 'stop', 'decline it']);

/** `pending`: a tool is waiting for a yes or no, so those words answer it instead of going to the strategist. */
export function parseVoice(said: string, ctx: { pending: boolean }): VoiceCmd {
  const n = norm(said);
  if (STOP_LISTENING.has(n)) return { kind: 'stop-listening' };
  if (ctx.pending) { if (APPROVE.has(n)) return { kind: 'approve' }; if (DECLINE.has(n)) return { kind: 'decline' }; }
  if (STOP.has(n)) return { kind: 'stop' };
  return { kind: 'text', text: said.trim() };
}

const RULE = /^\s*(?:[-*_=]\s*){3,}$/;                         // --- *** ___ === - - -
const TABLE_ROW = /^\s*\|.*\|\s*$|^[^|\n]+(?:\|[^|\n]+)+$/;     // | a | b |   or   a | b | c
const TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$/;   // |---|:--:|

/** Tables become one spoken line per row ("Name, 12, fast."): the lines and bars are layout, not words. */
function flattenTables(text: string): string {
  const out: string[] = []; let inTable = false;
  for (const line of text.split('\n')) {
    if (TABLE_RULE.test(line) && line.includes('-') && (line.includes('|') || inTable)) continue;
    if (TABLE_ROW.test(line) && line.includes('|')) {
      const cells = line.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim()).filter(Boolean);
      if (cells.length) { out.push(cells.join(', ') + '.'); inTable = true; continue; }
    }
    inTable = false; out.push(line);
  }
  return out.join('\n');
}

/** An answer as spoken sentences: no Markdown marks, tables, rules, dashes or bars, no [R1] citations, no code, links as their words. */
export function plainForSpeech(md: string): string[] {
  const t = flattenTables((md || '').replace(/\r/g, ''))
    .replace(/```[\s\S]*?```/g, ' (code omitted) ')
    .split('\n').filter(l => !RULE.test(l)).join('\n')
    .replace(/\[R\d+\]/g, '')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/https?:\/\/\S+/g, 'a link')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\$\$?([^$\n]+)\$\$?/g, '$1')                      // inline maths: say k, not "dollar k dollar"
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*(?:[-*•+]|\d+[.)])\s+/gm, '')
    .replace(/(\*\*|__|\*|_)(\S[^*_]*?)\1/g, '$2')
    .replace(/\s*(?:—|–|―|--+)\s*/g, ', ')                       // a dash used as a pause becomes a pause
    .replace(/(\s)-(\s)/g, ', ')                                // " - " between words too; hyphens inside words stay
    .replace(/\s*(?:->|=>|→|⇒)\s*/g, ' to ')
    .replace(/[|~^]+/g, ' ')                                      // stray bars and marks
    .replace(/\*+/g, '')
    .replace(/\s+([.,;:!?])/g, '$1').replace(/,(\s*,)+/g, ',').replace(/\s+,/g, ',').replace(/,\s*([.!?])/g, '$1').replace(/^[,\s]+/gm, '')
    .replace(/[ \t]+/g, ' ');
  return t.split(/\n{2,}|\n/).map(p => p.trim()).filter(p => /[\p{L}\p{N}]/u.test(p));
}
