<template>
  <div id="waziscope-app">

    <!-- ── Nav ──────────────────────────────────────────────────────────── -->
    <header class="nav">
      <div class="nav__inner">
        <router-link to="/" class="nav__logo">
          <span class="nav__logo-mark">
            <DownloadCloud :size="16" />
          </span>
          <span class="nav__logo-text">Wazi<em>Scope</em></span>
        </router-link>

        <nav class="nav__links">
          <router-link to="/" class="nav__item">
            <Home :size="15" />
            <span>Accueil</span>
          </router-link>
          <router-link to="/history" class="nav__item">
            <Clock :size="15" />
            <span>Historique</span>
            <span v-if="historyCount > 0" class="nav__badge">{{ historyCount }}</span>
          </router-link>
        </nav>
      </div>
    </header>

    <!-- ── Toasts ────────────────────────────────────────────────────────── -->
    <transition-group name="toast" tag="div" class="toasts">
      <div v-for="t in toasts" :key="t.id" :class="['toast', `toast--${t.type}`]">
        <component :is="toastIcon(t.type)" :size="15" />
        <span>{{ t.message }}</span>
      </div>
    </transition-group>

    <!-- ── Router View ───────────────────────────────────────────────────── -->
    <main>
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" @notify="showToast" />
        </transition>
      </router-view>
    </main>

    <!-- ── PWA Install Banner ────────────────────────────────────────────── -->
    <transition name="slide-up">
      <div v-if="showInstall" class="install-bar">
        <div class="install-bar__left">
          <span class="install-bar__icon"><Smartphone :size="20" /></span>
          <div>
            <strong>Installer WaziScope</strong>
            <p>Apparaît dans "Partager" pour télécharger en 1 tap</p>
          </div>
        </div>
        <div class="install-bar__actions">
          <button class="wz-btn wz-btn--mint wz-btn--sm" @click="installPWA">Installer</button>
          <button class="wz-btn wz-btn--ghost wz-btn--sm" @click="dismissInstall">
            <X :size="14" />
          </button>
        </div>
      </div>
    </transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide } from 'vue'
import { useRouter } from 'vue-router'
import {
  DownloadCloud, Home, Clock, CheckCircle2, AlertCircle,
  Info, X, Smartphone
} from 'lucide-vue-next'

const router = useRouter()

// ─── Toasts ──────────────────────────────────────────────────────────────────
const toasts = ref([])
let toastId  = 0

const toastIcon = (type) => ({
  success: CheckCircle2,
  danger:  AlertCircle,
  warning: AlertCircle,
  info:    Info,
}[type] || Info)

const showToast = ({ message, type = 'info' }) => {
  const id = ++toastId
  toasts.value.push({ id, message, type })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, 3500)
}
provide('notify', showToast)

// ─── Historique count ─────────────────────────────────────────────────────────
const historyCount = computed(() => {
  try { return JSON.parse(localStorage.getItem('wzs_history') || '[]').length } catch { return 0 }
})

// ─── PWA Install ─────────────────────────────────────────────────────────────
const deferredPrompt = ref(null)
const showInstall    = ref(false)

onMounted(() => {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
  const dismissed    = localStorage.getItem('wzs_install_dismissed')
  if (isStandalone || dismissed) return

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferredPrompt.value = e
    setTimeout(() => { showInstall.value = true }, 2500)
  })

  // Share Target via query param
  const params    = new URLSearchParams(window.location.search)
  const sharedUrl = params.get('shared')
  if (sharedUrl) router.push({ name: 'home', query: { url: sharedUrl } })

  navigator.serviceWorker?.addEventListener('message', (e) => {
    if (e.data?.type === 'SHARE_TARGET') {
      window.dispatchEvent(new CustomEvent('wzs:share', { detail: { url: e.data.url } }))
    }
  })
})

const installPWA = async () => {
  if (!deferredPrompt.value) return
  deferredPrompt.value.prompt()
  const { outcome } = await deferredPrompt.value.userChoice
  if (outcome === 'accepted') showToast({ message: 'WaziScope installé !', type: 'success' })
  deferredPrompt.value = null
  showInstall.value    = false
}

const dismissInstall = () => {
  showInstall.value = false
  localStorage.setItem('wzs_install_dismissed', '1')
}
</script>

<style>
/* ─────────────────────────────────────────────────────────────────────────────
   WAZISCOPE — Design System
   Fonts: Bricolage Grotesque (display) · Outfit (body) · Fira Code (mono)
   Accent: Mint #1bffa4 on near-black #080b0f
───────────────────────────────────────────────────────────────────────────── */

@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700;12..96,800&family=Outfit:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap');

:root {
  /* Surfaces */
  --bg:          #080b0f;
  --bg-1:        #0e1219;
  --bg-2:        #141a24;
  --bg-3:        #1b2233;

  /* Borders */
  --border:      rgba(255,255,255,0.06);
  --border-md:   rgba(255,255,255,0.11);
  --border-hi:   rgba(255,255,255,0.2);

  /* Accent — mint */
  --mint:        #1bffa4;
  --mint-dim:    rgba(27,255,164,0.12);
  --mint-glow:   rgba(27,255,164,0.25);

  /* Platform palette */
  --col-tiktok:    #ff2d55;
  --col-youtube:   #ff0033;
  --col-pinterest: #e60023;
  --col-facebook:  #1877f2;
  --col-instagram: #e1306c;
  --col-linkedin:  #0a66c2;
  --col-twitter:   #1da1f2;

  /* State */
  --success: #22c55e;
  --danger:  #f43f5e;
  --warning: #f59e0b;

  /* Text */
  --text-hi:  #eef2f8;
  --text-md:  #7a8499;
  --text-lo:  #3a4155;

  /* Radii */
  --r-sm:  6px;
  --r-md:  12px;
  --r-lg:  18px;
  --r-xl:  24px;
  --r-2xl: 32px;

  /* Fonts */
  --font-display: 'Bricolage Grotesque', sans-serif;
  --font-body:    'Outfit', sans-serif;
  --font-mono:    'Fira Code', monospace;

  --nav-h: 60px;
  --ease:  cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Reset ─────────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--bg);
  color: var(--text-hi);
  font-family: var(--font-body);
  font-size: 15px;
  line-height: 1.6;
  min-height: 100dvh;
  -webkit-font-smoothing: antialiased;
}
img { display: block; max-width: 100%; }
a   { color: inherit; text-decoration: none; }

/* ── Nav ───────────────────────────────────────────────────────────────────── */
.nav {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 100;
  height: var(--nav-h);
  border-bottom: 1px solid var(--border);
  background: rgba(8, 11, 15, 0.82);
  backdrop-filter: blur(18px) saturate(1.6);
}
.nav__inner {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 20px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav__logo {
  display: flex;
  align-items: center;
  gap: 9px;
}
.nav__logo-mark {
  width: 30px; height: 30px;
  background: var(--mint);
  border-radius: var(--r-sm);
  display: flex; align-items: center; justify-content: center;
  color: #000;
  flex-shrink: 0;
}
.nav__logo-text {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--text-hi);
}
.nav__logo-text em {
  font-style: normal;
  color: var(--mint);
}

.nav__links {
  display: flex;
  align-items: center;
  gap: 2px;
}
.nav__item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--r-sm);
  color: var(--text-md);
  font-size: 13.5px;
  font-weight: 500;
  transition: all 0.2s var(--ease);
}
.nav__item:hover, .nav__item.router-link-active {
  color: var(--text-hi);
  background: var(--bg-2);
}
.nav__item.router-link-active { color: var(--mint); }
.nav__badge {
  background: var(--mint);
  color: #000;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 20px;
  min-width: 16px;
  text-align: center;
}

/* ── Buttons ───────────────────────────────────────────────────────────────── */
.wz-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 11px 22px;
  border: none;
  border-radius: var(--r-md);
  font-family: var(--font-body);
  font-size: 14.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s var(--ease);
  white-space: nowrap;
}
.wz-btn--mint {
  background: var(--mint);
  color: #000;
}
.wz-btn--mint:hover  { opacity: 0.88; transform: translateY(-1px); }
.wz-btn--mint:active { transform: translateY(0); opacity: 1; }

.wz-btn--outline {
  background: transparent;
  color: var(--text-hi);
  border: 1px solid var(--border-md);
}
.wz-btn--outline:hover {
  border-color: var(--border-hi);
  background: var(--bg-2);
}

.wz-btn--ghost {
  background: transparent;
  color: var(--text-md);
}
.wz-btn--ghost:hover { background: var(--bg-2); color: var(--text-hi); }

.wz-btn--sm  { padding: 6px 14px; font-size: 13px; border-radius: var(--r-sm); }
.wz-btn--lg  { padding: 14px 30px; font-size: 16px; }
.wz-btn--blk { width: 100%; }
.wz-btn:disabled { opacity: 0.35; cursor: not-allowed; transform: none !important; }

/* ── Toasts ────────────────────────────────────────────────────────────────── */
.toasts {
  position: fixed;
  top: calc(var(--nav-h) + 14px);
  right: 16px;
  z-index: 300;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toast {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 16px;
  background: var(--bg-2);
  border: 1px solid var(--border-md);
  border-radius: var(--r-md);
  font-size: 13.5px;
  min-width: 240px;
  max-width: 320px;
  box-shadow: 0 8px 28px rgba(0,0,0,0.5);
  color: var(--text-hi);
}
.toast--success { border-color: var(--success); color: var(--success); }
.toast--danger  { border-color: var(--danger);  color: var(--danger); }
.toast--warning { border-color: var(--warning); color: var(--warning); }

.toast-enter-active, .toast-leave-active { transition: all 0.28s var(--ease); }
.toast-enter-from { opacity: 0; transform: translateX(16px); }
.toast-leave-to   { opacity: 0; transform: translateX(16px); }

/* ── Install bar ───────────────────────────────────────────────────────────── */
.install-bar {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  width: calc(100% - 32px);
  max-width: 480px;
  background: var(--bg-2);
  border: 1px solid var(--border-md);
  border-radius: var(--r-xl);
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.7);
}
.install-bar__left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}
.install-bar__icon {
  width: 38px; height: 38px;
  background: var(--mint-dim);
  color: var(--mint);
  border-radius: var(--r-sm);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.install-bar__left strong { display: block; font-size: 13.5px; font-weight: 600; }
.install-bar__left p      { font-size: 11.5px; color: var(--text-md); margin-top: 1px; }
.install-bar__actions     { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

.slide-up-enter-active { transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); }
.slide-up-leave-active { transition: all 0.22s var(--ease); }
.slide-up-enter-from   { opacity: 0; transform: translate(-50%, 20px); }
.slide-up-leave-to     { opacity: 0; transform: translate(-50%, 20px); }

/* ── Page transitions ──────────────────────────────────────────────────────── */
.page-enter-active { transition: all 0.22s var(--ease); }
.page-leave-active { transition: all 0.18s var(--ease); }
.page-enter-from   { opacity: 0; transform: translateY(6px); }
.page-leave-to     { opacity: 0; }

main { margin-top: var(--nav-h); min-height: calc(100dvh - var(--nav-h)); }

/* ── Scrollbar ─────────────────────────────────────────────────────────────── */
::-webkit-scrollbar       { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-lo); border-radius: 2px; }

/* ── Utility ───────────────────────────────────────────────────────────────── */
.container { max-width: 640px; margin: 0 auto; padding: 0 20px; }

/* Spinner */
@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 0.85s linear infinite; }
</style>
