<template>
  <div id="waziscope-app">
    <!-- Nav -->
    <nav class="nav-bar">
      <div class="nav-logo">
        <span class="logo-icon">⬇</span>
        <span class="logo-text">Wazi<em>Scope</em></span>
      </div>
      <div class="nav-links">
        <router-link to="/" class="nav-link">Accueil</router-link>
        <router-link to="/history" class="nav-link">
          Historique
          <span v-if="historyCount > 0" class="badge">{{ historyCount }}</span>
        </router-link>
      </div>
    </nav>

    <!-- Toast notifications -->
    <transition-group name="toast" tag="div" class="toast-container">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :class="['toast', `toast--${toast.type}`]"
      >
        <span class="toast-icon">{{ toast.icon }}</span>
        <span class="toast-msg">{{ toast.message }}</span>
      </div>
    </transition-group>

    <!-- Router View -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" @notify="showToast" />
        </transition>
      </router-view>
    </main>

    <!-- Install PWA Banner -->
    <transition name="slide-up">
      <div v-if="showInstallBanner" class="install-banner">
        <div class="install-banner__content">
          <span class="install-banner__icon">📲</span>
          <div class="install-banner__text">
            <strong>Installer WaziScope</strong>
            <p>Apparaît dans "Partager" pour télécharger directement</p>
          </div>
        </div>
        <div class="install-banner__actions">
          <button @click="installPWA" class="btn btn--primary btn--sm">Installer</button>
          <button @click="dismissInstall" class="btn btn--ghost btn--sm">Plus tard</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ─── Toasts ──────────────────────────────────────────────────────────────────
const toasts = ref([])
let toastId = 0

const showToast = ({ message, type = 'info', icon = 'ℹ️' }) => {
  const id = ++toastId
  toasts.value.push({ id, message, type, icon })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, 3500)
}
provide('notify', showToast)

// ─── Historique ───────────────────────────────────────────────────────────────
const historyCount = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('waziscope_history') || '[]').length
  } catch { return 0 }
})

// ─── Install PWA ──────────────────────────────────────────────────────────────
const deferredPrompt = ref(null)
const showInstallBanner = ref(false)

onMounted(() => {
  // Vérifier si déjà installé ou si banner déjà rejeté
  const dismissed = localStorage.getItem('install_dismissed')
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches

  if (isStandalone || dismissed) return

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferredPrompt.value = e
    setTimeout(() => { showInstallBanner.value = true }, 2000)
  })

  // Share Target : URL passée via query param ?shared=
  const params = new URLSearchParams(window.location.search)
  const sharedUrl = params.get('shared')
  if (sharedUrl) {
    router.push({ name: 'home', query: { url: sharedUrl } })
  }

  // Écouter les events du SW
  window.addEventListener('waziscope:share', (e) => {
    router.push({ name: 'home', query: { url: e.detail.url } })
  })
})

const installPWA = async () => {
  if (!deferredPrompt.value) return
  deferredPrompt.value.prompt()
  const { outcome } = await deferredPrompt.value.userChoice
  if (outcome === 'accepted') {
    showToast({ message: 'WaziScope installé !', type: 'success', icon: '✅' })
  }
  deferredPrompt.value = null
  showInstallBanner.value = false
}

const dismissInstall = () => {
  showInstallBanner.value = false
  localStorage.setItem('install_dismissed', '1')
}
</script>

<style>
/* ─── CSS Variables ─────────────────────────────────────────────────────────── */
:root {
  --bg:           #0a0a0f;
  --bg-card:      #13131a;
  --bg-hover:     #1a1a24;
  --border:       rgba(255,255,255,0.07);
  --border-hover: rgba(255,255,255,0.15);

  /* Accents per platform */
  --tiktok:    #ff0050;
  --pinterest: #e60023;
  --facebook:  #1877f2;
  --success:   #22c55e;
  --warning:   #f59e0b;
  --danger:    #ef4444;

  /* Primary gradient */
  --grad: linear-gradient(135deg, #ff0050 0%, #7928ca 50%, #1877f2 100%);

  --text:     #f0f0f5;
  --text-muted: #6b6b80;
  --text-dim:   #3a3a50;

  --radius:   16px;
  --radius-sm: 8px;
  --radius-lg: 24px;

  --font-display: 'Syne', sans-serif;
  --font-body:    'DM Sans', sans-serif;
  --font-mono:    'JetBrains Mono', monospace;

  --nav-height: 64px;
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ─── Reset ──────────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 15px;
  line-height: 1.6;
  min-height: 100dvh;
  -webkit-font-smoothing: antialiased;
}

@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

/* ─── Nav ─────────────────────────────────────────────────────────────────────── */
.nav-bar {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  height: var(--nav-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(10, 10, 15, 0.85);
  backdrop-filter: blur(20px) saturate(1.5);
  border-bottom: 1px solid var(--border);
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  text-decoration: none;
}
.logo-icon {
  width: 32px; height: 32px;
  background: var(--grad);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.logo-text em {
  font-style: normal;
  background: var(--grad);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition);
}
.nav-link:hover,
.nav-link.router-link-active {
  color: var(--text);
  background: var(--bg-hover);
}
.badge {
  background: var(--tiktok);
  color: white;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 20px;
  min-width: 18px;
  text-align: center;
}

/* ─── Main ────────────────────────────────────────────────────────────────────── */
.main-content {
  margin-top: var(--nav-height);
  min-height: calc(100dvh - var(--nav-height));
}

/* ─── Buttons ─────────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  border: none;
  border-radius: var(--radius);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition);
  text-decoration: none;
  white-space: nowrap;
}
.btn--primary {
  background: var(--grad);
  color: white;
}
.btn--primary:hover { opacity: 0.9; transform: translateY(-1px); }
.btn--primary:active { transform: translateY(0); }

.btn--ghost {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
}
.btn--ghost:hover {
  border-color: var(--border-hover);
  color: var(--text);
  background: var(--bg-hover);
}

.btn--sm { padding: 7px 16px; font-size: 13px; border-radius: var(--radius-sm); }
.btn--lg { padding: 16px 32px; font-size: 17px; }
.btn--block { width: 100%; }

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none !important;
}

/* ─── Toasts ──────────────────────────────────────────────────────────────────── */
.toast-container {
  position: fixed;
  top: calc(var(--nav-height) + 12px);
  right: 16px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  min-width: 260px;
  max-width: 340px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.toast--success { border-color: var(--success); }
.toast--danger  { border-color: var(--danger); }
.toast--warning { border-color: var(--warning); }

.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from { opacity: 0; transform: translateX(20px); }
.toast-leave-to   { opacity: 0; transform: translateX(20px); }

/* ─── Install Banner ──────────────────────────────────────────────────────────── */
.install-banner {
  position: fixed;
  bottom: 24px; left: 50%;
  transform: translateX(-50%);
  z-index: 150;
  width: calc(100% - 32px);
  max-width: 480px;
  background: var(--bg-card);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  box-shadow: 0 16px 48px rgba(0,0,0,0.6);
}
.install-banner__content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}
.install-banner__icon { font-size: 24px; }
.install-banner__text strong { display: block; font-size: 14px; color: var(--text); }
.install-banner__text p { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.install-banner__actions { display: flex; gap: 8px; flex-shrink: 0; }

.slide-up-enter-active { transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); }
.slide-up-leave-active { transition: all 0.25s ease; }
.slide-up-enter-from  { opacity: 0; transform: translate(-50%, 20px); }
.slide-up-leave-to    { opacity: 0; transform: translate(-50%, 20px); }

/* ─── Page transitions ────────────────────────────────────────────────────────── */
.page-enter-active { transition: all 0.25s ease; }
.page-leave-active { transition: all 0.2s ease; }
.page-enter-from   { opacity: 0; transform: translateY(8px); }
.page-leave-to     { opacity: 0; transform: translateY(-4px); }

/* ─── Scrollbar ───────────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-dim); border-radius: 3px; }
</style>
