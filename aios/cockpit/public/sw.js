/* Le service worker de Hakim (2026-10-20) : il reçoit les notifications du cockpit (Web Push) même quand la
   page est fermée — une relance de Hakim, le résultat d'un agent — et rouvre la page Parler au toucher. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { corps: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.titre || 'Hakim', {
    body: d.corps || '', tag: d.tag || 'hakim', renotify: true, icon: '/icone-192.png', badge: '/icone-192.png',
    data: { url: d.url || '/parler' },
  }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  // seulement une page du cockpit (relecture du 2026-10-20 : jamais une adresse venue d'ailleurs)
  let url = (e.notification.data && e.notification.data.url) || '/parler';
  try { const u = new URL(url, self.location.origin); url = u.origin === self.location.origin ? u.pathname : '/parler'; } catch (_) { url = '/parler'; }
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((fenetres) => {
    for (const f of fenetres) if (new URL(f.url).pathname === url && 'focus' in f) return f.focus();
    return self.clients.openWindow(url);
  }));
});
