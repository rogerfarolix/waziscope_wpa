<template>
  <div class="history-page">
    <div class="container">
      <div class="page-header">
        <div>
          <h1 class="page-title">Historique</h1>
          <p class="page-sub">{{ items.length }} vidéo{{ items.length > 1 ? 's' : '' }} téléchargée{{ items.length > 1 ? 's' : '' }}</p>
        </div>
        <button v-if="items.length" @click="clearHistory" class="btn btn--ghost btn--sm">
          🗑 Tout effacer
        </button>
      </div>

      <!-- Liste -->
      <div v-if="items.length" class="history-list">
        <div
          v-for="item in items"
          :key="item.id"
          class="history-item"
        >
          <div class="history-thumb">
            <img v-if="item.thumbnail" :src="item.thumbnail" :alt="item.title" />
            <div v-else class="no-thumb">{{ getPlatformIcon(item.platform) }}</div>
            <span :class="['platform-dot', `platform-dot--${item.platform}`]"></span>
          </div>
          <div class="history-info">
            <p class="history-title">{{ item.title }}</p>
            <span class="history-date">{{ formatDate(item.date) }}</span>
          </div>
          <a
            v-if="item.url"
            :href="`/api/v1/download?url=${encodeURIComponent(item.url)}&filename=${encodeURIComponent(item.title + '.mp4')}`"
            :download="item.title + '.mp4'"
            class="btn btn--ghost btn--sm"
          >⬇</a>
          <button @click="removeItem(item.id)" class="btn btn--ghost btn--sm history-del">✕</button>
        </div>
      </div>

      <!-- Vide -->
      <div v-else class="empty-state">
        <div class="empty-icon">📂</div>
        <h3>Aucun téléchargement</h3>
        <p>Les vidéos que tu télécharges apparaîtront ici</p>
        <router-link to="/" class="btn btn--primary">Télécharger une vidéo</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const items = ref([])

onMounted(() => {
  items.value = JSON.parse(localStorage.getItem('waziscope_history') || '[]')
})

const removeItem = (id) => {
  items.value = items.value.filter(i => i.id !== id)
  localStorage.setItem('waziscope_history', JSON.stringify(items.value))
}

const clearHistory = () => {
  items.value = []
  localStorage.removeItem('waziscope_history')
}

const formatDate = (iso) => {
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  if (diff < 60000)      return 'À l\'instant'
  if (diff < 3600000)    return `Il y a ${Math.floor(diff / 60000)} min`
  if (diff < 86400000)   return `Il y a ${Math.floor(diff / 3600000)}h`
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
}

const getPlatformIcon = (p) => ({ tiktok: '🎵', pinterest: '📌', facebook: '📘' })[p] || '🎬'
</script>

<style scoped>
.history-page { padding: 32px 0 64px; }
.container { max-width: 600px; margin: 0 auto; padding: 0 20px; }

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;
}
.page-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 800;
}
.page-sub { color: var(--text-muted); font-size: 14px; margin-top: 4px; }

.history-list { display: flex; flex-direction: column; gap: 10px; }

.history-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: border-color var(--transition);
}
.history-item:hover { border-color: var(--border-hover); }

.history-thumb {
  position: relative;
  width: 64px; height: 48px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-hover);
}
.history-thumb img { width: 100%; height: 100%; object-fit: cover; }
.no-thumb {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.platform-dot {
  position: absolute;
  bottom: 3px; right: 3px;
  width: 8px; height: 8px;
  border-radius: 50%;
}
.platform-dot--tiktok    { background: var(--tiktok); }
.platform-dot--pinterest { background: var(--pinterest); }
.platform-dot--facebook  { background: var(--facebook); }

.history-info { flex: 1; min-width: 0; }
.history-title {
  font-size: 13px; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.history-date { font-size: 11px; color: var(--text-muted); }
.history-del { color: var(--text-dim); }
.history-del:hover { color: var(--danger); border-color: var(--danger); }

.empty-state {
  text-align: center;
  padding: 80px 24px;
  color: var(--text-muted);
}
.empty-icon { font-size: 56px; margin-bottom: 16px; }
.empty-state h3 { font-family: var(--font-display); font-size: 20px; color: var(--text); margin-bottom: 8px; }
.empty-state p { margin-bottom: 24px; }
</style>
