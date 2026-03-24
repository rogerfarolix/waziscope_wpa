/**
 * WaziScope — Vue.js PWA  v2
 * Point d'entrée principal
 *
 * Dépendances à installer :
 *   npm install vue-router axios lucide-vue-next
 *   (shadcn-vue optionnel : npx shadcn-vue@latest init)
 */

import { createApp }                       from 'vue'
import { createRouter, createWebHistory }  from 'vue-router'
import App                                 from './App.vue'
import HomeView                            from './views/HomeView.vue'
import ShareView                           from './views/ShareView.vue'
import HistoryView                         from './views/HistoryView.vue'
import axios                               from 'axios'

// ─── Axios defaults ───────────────────────────────────────────────────────────
axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest'

// Intercepteur : erreurs réseau lisibles
axios.interceptors.response.use(
    (r) => r,
    (err) => {
        if (!err.response) {
            err.message = 'Impossible de joindre le serveur. Vérifiez votre connexion.'
        }
        return Promise.reject(err)
    }
)

// ─── Router ───────────────────────────────────────────────────────────────────
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/',        component: HomeView,    name: 'home'    },
        { path: '/share',   component: ShareView,   name: 'share'   },
        { path: '/history', component: HistoryView, name: 'history' },
        // Fallback → Home
        { path: '/:pathMatch(.*)*', redirect: '/' },
    ],
    scrollBehavior: () => ({ top: 0 }),
})

// ─── Service Worker ───────────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        try {
            const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
            console.log('[WaziScope] SW enregistré:', reg.scope)

            // Mettre à jour le SW quand une nouvelle version est disponible
            reg.addEventListener('updatefound', () => {
                const newWorker = reg.installing
                newWorker?.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        console.log('[WaziScope] Nouvelle version disponible — rechargez.')
                    }
                })
            })
        } catch (e) {
            console.error('[WaziScope] SW erreur:', e)
        }
    })

    // Écouter les messages du SW (Share Target)
    navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SHARE_TARGET') {
            window.dispatchEvent(
                new CustomEvent('wzs:share', { detail: { url: event.data.url } })
            )
        }
    })
}

// ─── App ──────────────────────────────────────────────────────────────────────
const app = createApp(App)
app.use(router)
app.mount('#app')
