<template>
  <div class="history">
    <div class="container">

      <!-- Header -->
      <div class="page-hd">
        <div>
          <h1 class="page-title">Historique</h1>
          <p class="page-sub">
            {{ items.length }}
            téléchargement{{ items.length !== 1 ? 's' : '' }}
          </p>
        </div>
        <button v-if="items.length" class="wz-btn wz-btn--ghost wz-btn--sm" @click="clearAll">
          <Trash2 :size="13" />
          Tout effacer
        </button>
      </div>

      <!-- List -->
      <transition-group name="hist" tag="div" class="hist-list" v-if="items.length">
        <div v-for="item in items" :key="item.id" class="hist-item">

          <!-- Thumb -->
          <div class="hist-thumb">
            <img v-if="item.thumbnail" :src="item.thumbnail" :alt="item.title" />
            <div v-else class="hist-thumb__fallback">
              <component :is="platformIcon(item.platform)" :size="20" />
            </div>
            <span :class="['hist-plat', `hist-plat--${item.platform}`]">
              <component :is="platformIcon(item.platform)" :size="10" />
            </span>
          </div>

          <!-- Info -->
          <div class="hist-info">
            <p class="hist-title">{{ item.title }}</p>
            <span class="hist-date">
              <Clock :size="11" />
              {{ fmtDate(item.date) }}
            </span>
          </div>

          <!-- Actions -->
          <div class="hist-actions">
            <a
              v-if="item.url"
              :href="`/api/v1/download?url=${encodeURIComponent(item.url)}&filename=${encodeURIComponent(item.title + '.mp4')}`"
              :download="item.title + '.mp4'"
              class="wz-btn wz-btn--outline wz-btn--sm"
            >
              <Download :size="13" />
            </a>
            <button class="wz-btn wz-btn--ghost wz-btn--sm del-btn" @click="remove(item.id)">
              <X :size="13" />
            </button>
          </div>
        </div>
      </transition-group>

      <!-- Empty state -->
      <div v-else class="empty">
        <div class="empty__icon">
          <ClockFading :size="36" />
        </div>
        <h3 class="empty__title">Aucun téléchargement</h3>
        <p class="empty__sub">Les vidéos que tu télécharges apparaîtront ici</p>
        <router-link to="/" class="wz-btn wz-btn--mint">
          <DownloadCloud :size="15" />
          Télécharger une vidéo
        </router-link>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  Clock, Trash2, Download, X, DownloadCloud,
  Music2, Youtube, Pin, Facebook, Instagram, Linkedin, Twitter, Film
} from 'lucide-vue-next'

// Lucide doesn't have ClockFading, use Clock with opacity
import { Clock as ClockFading } from 'lucide-vue-next'

const items = ref([])

onMounted(() => {
  items.value = JSON.parse(localStorage.getItem('wzs_history') || '[]')
})

const remove = (id) => {
  items.value = items.value.filter(i => i.id !== id)
  localStorage.setItem('wzs_history', JSON.stringify(items.value))
}

const clearAll = () => {
  items.value = []
  localStorage.removeItem('wzs_history')
}

const platformIcon = (id) => ({
  tiktok: Music2, youtube: Youtube, pinterest: Pin,
  facebook: Facebook, instagram: Instagram,
  linkedin: Linkedin, twitter: Twitter,
}[id] || Film)

const fmtDate = (iso) => {
  const d    = new Date(iso)
  const diff = Date.now() - d
  if (diff < 60000)    return 'À l\'instant'
  if (diff < 3600000)  return `Il y a ${Math.floor(diff / 60000)} min`
  if (diff < 86400000) return `Il y a ${Math.floor(diff / 3600000)} h`
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
}
</script>

<style scoped>
.history  { padding: 36px 0 80px; }

/* Header */
.page-hd  {
  display: flex; align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;
  gap: 12px;
}
.page-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 800;
}
.page-sub { color: var(--text-md); font-size: 13.5px; margin-top: 3px; }

/* List */
.hist-list { display: flex; flex-direction: column; gap: 8px; }

.hist-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  transition: border-color 0.18s var(--ease);
}
.hist-item:hover { border-color: var(--border-md); }

.hist-thumb {
  position: relative;
  width: 64px; height: 48px;
  border-radius: var(--r-sm);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-2);
}
.hist-thumb img { width: 100%; height: 100%; object-fit: cover; }
.hist-thumb__fallback {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-lo);
}

.hist-plat {
  position: absolute;
  bottom: 3px; right: 3px;
  width: 16px; height: 16px;
  border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
}
.hist-plat--tiktok    { background: var(--col-tiktok); }
.hist-plat--youtube   { background: var(--col-youtube); }
.hist-plat--pinterest { background: var(--col-pinterest); }
.hist-plat--facebook  { background: var(--col-facebook); }
.hist-plat--instagram { background: var(--col-instagram); }
.hist-plat--linkedin  { background: var(--col-linkedin); }
.hist-plat--twitter   { background: var(--col-twitter); }

.hist-info { flex: 1; min-width: 0; }
.hist-title {
  font-size: 13px; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 3px;
}
.hist-date {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: var(--text-md);
}

.hist-actions { display: flex; gap: 5px; flex-shrink: 0; }
.del-btn { color: var(--text-lo); }
.del-btn:hover { color: var(--danger) !important; }

/* Empty */
.empty {
  text-align: center;
  padding: 80px 20px;
}
.empty__icon {
  width: 72px; height: 72px;
  background: var(--bg-2);
  border-radius: var(--r-xl);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-lo);
  margin: 0 auto 20px;
}
.empty__title {
  font-family: var(--font-display);
  font-size: 20px; font-weight: 700;
  margin-bottom: 8px;
}
.empty__sub { color: var(--text-md); font-size: 14px; margin-bottom: 24px; }

/* Transitions */
.hist-enter-active { transition: all 0.28s var(--ease); }
.hist-leave-active { transition: all 0.22s var(--ease); position: absolute; width: 100%; }
.hist-enter-from   { opacity: 0; transform: translateX(-8px); }
.hist-leave-to     { opacity: 0; transform: translateX(8px); }
.hist-move         { transition: transform 0.28s var(--ease); }
</style>
