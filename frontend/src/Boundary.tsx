import { Component, ReactNode } from 'react';
import { isChunkError, reloadOnce } from './chunkError';

/** If a page fails to load or crashes, the rest of the app (menu, banners) stays, with a way out: reload, or go somewhere else. */
export default class Boundary extends Component<{ children: ReactNode; resetKey: string }, { error: unknown }> {
  state = { error: null as unknown };
  static getDerivedStateFromError(error: unknown) { return { error }; }
  componentDidCatch(error: unknown) { if (isChunkError(error)) reloadOnce(); }                     // an old window after an update fixes itself
  componentDidUpdate(prev: { resetKey: string }) { if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null }); }   // moving to another page tries again
  render() {
    if (!this.state.error) return this.props.children;
    const updated = isChunkError(this.state.error);
    return (
      <div className="flex h-full items-center justify-center p-8 text-center" role="alert"><div className="max-w-sm">
        <div className="mb-2 text-lg font-medium">{updated ? 'SmartWard was updated' : 'This page hit a problem'}</div>
        <p className="mb-4 text-sm text-zinc-500">{updated ? 'This window was showing an older version. Reloading brings it up to date.' : 'The rest of the app still works: pick another page from the menu, or reload.'}</p>
        <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500" onClick={() => location.reload()}>Reload</button>
        {!updated && <details className="mt-3 text-left text-xs text-zinc-500"><summary className="cursor-pointer">Details</summary><code className="break-all">{String((this.state.error as any)?.message ?? this.state.error)}</code></details>}
      </div></div>
    );
  }
}
