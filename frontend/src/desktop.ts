/** Bridges to the native shell when SmartWard runs in its own window (Tauri); harmless in a browser. */
export const isDesktop = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

export async function desktopCall<T = unknown>(command: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(command, args);
}

/** Listens for an event from the shell (for example the tray's "Lock now"); returns a function that stops listening. */
export async function onDesktopEvent(name: string, callback: () => void): Promise<() => void> {
  if (!isDesktop) return () => {};
  const { listen } = await import('@tauri-apps/api/event');
  return listen(name, callback);
}
