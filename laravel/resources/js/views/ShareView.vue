<template>
  <div class="share-page">
    <div class="share-card">

      <!-- Animated ring -->
      <div class="ring-wrap" aria-hidden="true">
        <div class="ring ring--outer"></div>
        <div class="ring ring--inner"></div>
        <span class="ring-icon">
          <DownloadCloud :size="28" />
        </span>
      </div>

      <div class="share-copy">
        <h2 class="share-title">Réception en cours…</h2>
        <p class="share-sub">Extraction automatique du lien partagé</p>
      </div>

      <!-- URL preview -->
      <div v-if="displayUrl" class="share-url-wrap">
        <Link2 :size="12" />
        <span class="share-url">{{ displayUrl }}</span>
      </div>

    </div>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DownloadCloud, Link2 } from 'lucide-vue-next'

const route  = useRoute()
const router = useRouter()

const sharedUrl = computed(() => {
  let url = route.query.url || route.query.text || route.query.shared || ''
  // TikTok met parfois l'URL dans le champ "text" avec du texte autour
  if (url && !String(url).startsWith('http')) {
    const match = String(url).match(/https?:\/\/[^\s]+/)
    if (match) url = match[0]
  }
  return String(url)
})

const displayUrl = computed(() => {
  const u = sharedUrl.value
  return u.length > 55 ? u.substring(0, 55) + '…' : u
})

onMounted(() => {
  setTimeout(() => {
    router.replace({
      name:  'home',
      query: { url: sharedUrl.value || '' },
    })
  }, 900)
})
</script>

<style scoped>
.share-page {
  min-height: calc(100dvh - var(--nav-h));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.share-card {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
  max-width: 320px;
}

/* Ring animation */
.ring-wrap {
  position: relative;
  width: 90px; height: 90px;
  display: flex; align-items: center; justify-content: center;
}

.ring {
  position: absolute; inset: 0;
  border-radius: 50%;
  border: 2px solid transparent;
}
.ring--outer {
  border-top-color: var(--mint);
  border-right-color: rgba(27,255,164,0.3);
  animation: spin 1.1s linear infinite;
}
.ring--inner {
  inset: 12px;
  border-bottom-color: rgba(27,255,164,0.5);
  border-left-color: transparent;
  animation: spin 0.75s linear infinite reverse;
}

.ring-icon {
  color: var(--mint);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%       { transform: scale(1.12); opacity: 0.75; }
}

.share-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
}
.share-sub { font-size: 13.5px; color: var(--text-md); margin-top: -14px; }

.share-url-wrap {
  display: flex; align-items: center; gap: 7px;
  background: var(--bg-1);
  border: 1px solid var(--border-md);
  border-radius: var(--r-md);
  padding: 9px 14px;
  max-width: 100%;
}
.share-url {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text-md);
  word-break: break-all;
  text-align: left;
}
</style>
