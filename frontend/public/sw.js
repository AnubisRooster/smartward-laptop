// SmartWard's service worker: lets the installed app open when the network is slow. It only keeps the app's own files
// (page, scripts, icons), network first, so an update always wins. It never touches /api/, so no article or chat is stored here.
const CACHE = 'smartward-shell-v1';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;
  e.respondWith(fetch(e.request).then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); } return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match('/'))));
});

// Phone notifications. The laptop only ever sends generic text ("2 watch matches"); details are shown once SmartWard is open.
self.addEventListener('push', e => {
  let d = {}; try { d = e.data ? e.data.json() : {}; } catch { /* not JSON: show the default */ }
  e.waitUntil(self.registration.showNotification(d.title || 'SmartWard', { body: d.body || 'Open SmartWard to see what’s new.', tag: d.tag || 'smartward', icon: '/icon-192.png', badge: '/icon-192.png', data: { url: typeof d.url === 'string' && d.url.startsWith('/') ? d.url : '/' } }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data?.url || '/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
    const c = cs.find(w => new URL(w.url).origin === location.origin);
    return c ? c.focus().then(w => w.navigate ? w.navigate(url) : w) : self.clients.openWindow(url);
  }));
});
