import { errText, post } from './api';
import { toast } from './feedback';
import { useNav } from './hooks';

/** Starts a chat about an article and opens it; the strategist answers straight away. */
export async function discussArticle(id: number) {
  try { const r = await post('/articles/' + id + '/discuss'); useNav.getState().go('chat', { convId: r.id }); }
  catch (e) { toast.error(errText(e)); }
}
