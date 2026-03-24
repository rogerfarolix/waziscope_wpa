/**
 * WaziScope Service Worker v2
 * ─ Cache offline
 * ─ Share Target (intercepte les partages depuis TikTok, YouTube, etc.)
 * ─ Background Sync prêt
 */

const CACHE_NAME    = 'wzs-v2'
const OFFLINE_URL   = '/offline.html'

const PRECACHE_URLS = [
    '/',
    '/manifest.json',
    '/offline.html',
]

// ─── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((c) => c.addAll(PRECACHE_URLS))
    )
    // Forcer l'activation immédiate (pas besoin de fermer l'onglet)
    self.skipWaiting()
})

// ─── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    )
    self.clients.claim()
})

// ─── Fetch ────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (e) => {
    const url = new URL(e.request.url)

    // ── 1. Share Target (/share?url=...) ──────────────────────────────────
    if (url.pathname === '/share' && e.request.method === 'GET') {
        e.respondWith(handleShareTarget(url))
        return
    }

    // ── 2. API calls → Network First (no cache) ───────────────────────────
    if (url.pathname.startsWith('/api/')) {
        e.respondWith(networkOnly(e.request))
        return
    }

    // ── 3. Font / CDN → Cache First ───────────────────────────────────────
    if (url.hostname.includes('fonts.g') || url.hostname.includes('gstatic')) {
        e.respondWith(cacheFirst(e.request))
        return
    }

    // ── 4. App shell → Stale-While-Revalidate ────────────────────────────
    e.respondWith(staleWhileRevalidate(e.request))
})

// ─── Share Target handler ─────────────────────────────────────────────────────
async function handleShareTarget(url) {
    // Récupérer l'URL partagée depuis les query params
    let sharedUrl = url.searchParams.get('url') || ''

    // Fallback: chercher une URL dans le champ "text"
    if (!sharedUrl || !sharedUrl.startsWith('http')) {
        const textParam = url.searchParams.get('text') || ''
        const match     = textParam.match(/https?:\/\/[^\s]+/)
        sharedUrl = match ? match[0] : (sharedUrl || textParam)
    }

    // Nettoyer les tracking params courants
    sharedUrl = cleanUrl(sharedUrl)

    // Notifier tous les clients Vue ouverts
    const clients = await self.clients.matchAll({ includeUncontrolled: true, type: 'window' })

    if (clients.length > 0) {
        // Envoyer le message à la première fenêtre ouverte
        clients[0].postMessage({ type: 'SHARE_TARGET', url: sharedUrl })
        // Focaliser la fenêtre si elle est minimisée
        try { await clients[0].focus() } catch { /* fenêtre ne peut pas être focalisée */ }
        return Response.redirect('/?shared=' + encodeURIComponent(sharedUrl), 303)
    }

    // Aucune fenêtre ouverte → ouvrir l'app
    await self.clients.openWindow('/?shared=' + encodeURIComponent(sharedUrl))
    return Response.redirect('/?shared=' + encodeURIComponent(sharedUrl), 303)
}

// Nettoyage des URLs de tracking courants (TikTok, YouTube...)
function cleanUrl(url) {
    if (!url) return url
    try {
        const u = new URL(url)
        // Supprimer les paramètres de tracking courants
        const trackingParams = [
            '_r', 'is_from_webapp', 'sender_device', 'share_app_name',
            'social_sharing_id', 'utm_source', 'utm_medium', 'utm_campaign',
            'si', 'feature', 'ab_channel',
        ]
        trackingParams.forEach((p) => u.searchParams.delete(p))
        return u.toString()
    } catch {
        return url
    }
}

// ─── Cache strategies ─────────────────────────────────────────────────────────

async function networkOnly(req) {
    try {
        return await fetch(req)
    } catch {
        return new Response(JSON.stringify({ success: false, message: 'Offline' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
        })
    }
}

async function cacheFirst(req) {
    const cached = await caches.match(req)
    if (cached) return cached

    try {
        const res = await fetch(req)
        if (res.ok) {
            const cache = await caches.open(CACHE_NAME)
            cache.put(req, res.clone())
        }
        return res
    } catch {
        return caches.match(OFFLINE_URL) || new Response('Offline')
    }
}

async function staleWhileRevalidate(req) {
    const cache  = await caches.open(CACHE_NAME)
    const cached = await cache.match(req)

    const fetchPromise = fetch(req).then((res) => {
        if (res.ok) cache.put(req, res.clone())
        return res
    }).catch(() => null)

    return cached || await fetchPromise || caches.match(OFFLINE_URL) || new Response('Offline')
}
