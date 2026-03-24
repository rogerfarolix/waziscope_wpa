/**
 * WaziScope - Vue.js PWA
 * Point d'entrée principal
 */

import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HomeView from './views/HomeView.vue'
import ShareView from './views/ShareView.vue'
import HistoryView from './views/HistoryView.vue'

// ─── Router ───────────────────────────────────────────────────────────────────
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/',       component: HomeView,    name: 'home' },
        { path: '/share',  component: ShareView,   name: 'share' },
        { path: '/history',component: HistoryView, name: 'history' },
    ]
})

// ─── Service Worker ───────────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        try {
            const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
            console.log('[WaziScope] SW enregistré:', reg.scope)
        } catch (e) {
            console.error('[WaziScope] SW erreur:', e)
        }
    })

    // Écouter les messages du SW (Share Target)
    navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SHARE_TARGET') {
            window.dispatchEvent(new CustomEvent('WaziScope:share', {
                detail: { url: event.data.url }
            }))
        }
    })
}

// ─── App ──────────────────────────────────────────────────────────────────────
const app = createApp(App)
app.use(router)
app.mount('#app')
