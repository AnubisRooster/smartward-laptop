import { get, post } from './api';

/** Turning phone notifications on and off for this device (Web Push through the phone's own push service). */
export const pushSupported = () => typeof navigator !== 'undefined' && 'serviceWorker' in navigator && typeof window !== 'undefined' && 'PushManager' in window && 'Notification' in window;

/** iPhone only allows notifications for a site added to the Home Screen and opened from there. */
export const needsHomeScreen = (ua = navigator.userAgent, standalone = (navigator as any).standalone === true || matchMedia('(display-mode: standalone)').matches) =>
  /iPhone|iPad|iPod/.test(ua) && !standalone;

export function keyBytes(b64url: string): Uint8Array {
  const b64 = (b64url + '='.repeat((4 - (b64url.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(b64), c => c.charCodeAt(0));
}

const label = () => /Android/.test(navigator.userAgent) ? 'Android phone' : /iPhone/.test(navigator.userAgent) ? 'iPhone' : /iPad/.test(navigator.userAgent) ? 'iPad' : 'Browser';

export async function currentSub(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration(); return reg ? reg.pushManager.getSubscription() : null;
}

export async function enablePush(): Promise<PushSubscription> {
  const perm = await Notification.requestPermission();
  if (perm !== 'granted') throw new Error(perm === 'denied' ? 'Notifications are blocked for SmartWard in this browser’s settings.' : 'Notifications weren’t allowed.');
  const { public_key } = await get('/push/key');
  const reg = await navigator.serviceWorker.ready;
  const sub = (await reg.pushManager.getSubscription()) || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) as BufferSource });
  await post('/push/subscribe', { subscription: sub.toJSON(), label: label() });
  return sub;
}

export async function disablePush(): Promise<void> {
  const sub = await currentSub(); if (!sub) return;
  await post('/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => {}); await sub.unsubscribe();
}

export const testPush = (sub: PushSubscription) => post('/push/test', { endpoint: sub.endpoint });
