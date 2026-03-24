/**
 * WaziScope Service Worker
 * Gère le cache offline et intercepte les Share Target
 */

const CACHE_NAME = 'waziscope-v1';
const OFFLINE_URL = '/offline.html';

const STATIC_ASSETS = [
    '/',
    '/manifest.json',
    '/offline.html',
];

// ─── Installation ─────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// ─── Activation ───────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

// ─── Fetch & Share Target ─────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Intercepter le Share Target (/share?url=...)
    if (url.pathname === '/share' && event.request.method === 'GET') {
        event.respondWith(handleShareTarget(url));
        return;
    }

    // Stratégie Network First pour les API
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirst(event.request));
        return;
    }

    // Stratégie Cache First pour les assets statiques
    event.respondWith(cacheFirst(event.request));
});

// ─── Gestion du Share Target ──────────────────────────────────────────────────
async function handleShareTarget(url) {
    // Extraire l'URL partagée (peut venir de ?url= ou ?text=)
    let sharedUrl = url.searchParams.get('url')
                 || url.searchParams.get('text')
                 || '';

    // Parfois le texte contient l'URL (ex: TikTok met le lien dans le text)
    if (!sharedUrl.startsWith('http')) {
        const textParam = url.searchParams.get('text') || '';
        const urlMatch = textParam.match(/https?:\/\/[^\s]+/);
        if (urlMatch) sharedUrl = urlMatch[0];
    }

    // Notifier tous les clients ouverts
    const clients = await self.clients.matchAll({ includeUncontrolled: true, type: 'window' });

    if (clients.length > 0) {
        clients[0].postMessage({ type: 'SHARE_TARGET', url: sharedUrl });
        // Rediriger vers la page principale
        return Response.redirect('/?shared=' + encodeURIComponent(sharedUrl), 303);
    }

    // Ouvrir l'app si pas de client ouvert
    await self.clients.openWindow('/?shared=' + encodeURIComponent(sharedUrl));
    return Response.redirect('/?shared=' + encodeURIComponent(sharedUrl), 303);
}

// ─── Stratégies de cache ──────────────────────────────────────────────────────
async function networkFirst(request) {
    try {
        const response = await fetch(request);
        return response;
    } catch {
        const cached = await caches.match(request);
        return cached || new Response(JSON.stringify({ error: 'Offline' }), {
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        return caches.match(OFFLINE_URL) || new Response('Offline');
    }
}
