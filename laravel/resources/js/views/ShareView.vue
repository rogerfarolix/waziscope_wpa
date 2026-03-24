<template>
  <div class="share-page">
    <div class="share-card">
      <div class="share-spinner">
        <div class="ring"></div>
        <span class="share-icon">⬇</span>
      </div>
      <h2 class="share-title">Réception en cours…</h2>
      <p class="share-url">{{ displayUrl }}</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route  = useRoute()
const router = useRouter()

const sharedUrl = computed(() => {
  return route.query.url
      || route.query.text
      || route.query.shared
      || ''
})

const displayUrl = computed(() => {
  const u = sharedUrl.value
  return u.length > 60 ? u.substring(0, 60) + '…' : u
})

onMounted(() => {
  // Extraire l'URL si elle est dans un texte (TikTok met parfois le lien dans "text")
  let url = sharedUrl.value
  if (url && !url.startsWith('http')) {
    const match = url.match(/https?:\/\/[^\s]+/)
    if (match) url = match[0]
  }

  // Rediriger vers Home avec l'URL pour lancer l'extraction auto
  setTimeout(() => {
    router.replace({ name: 'home', query: { url: url || '' } })
  }, 800)
})
</script>

<style scoped>
.share-page {
  min-height: calc(100dvh - var(--nav-height));
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
  gap: 20px;
}

.share-spinner {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 3px solid transparent;
  border-top-color: #ff0050;
  border-right-color: #7928ca;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.share-icon {
  font-size: 28px;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50%       { transform: scale(1.15); }
}

.share-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
}

.share-url {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  max-width: 320px;
  word-break: break-all;
}
</style>
