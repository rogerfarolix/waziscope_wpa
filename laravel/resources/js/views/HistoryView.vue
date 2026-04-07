<template>
  <div class="stats-page">
    <div class="container">

      <!-- Header -->
      <div class="page-hd">
        <div>
          <h1 class="page-title">Statistiques</h1>
          <p class="page-sub">Résumé de tes téléchargements</p>
        </div>
        <button v-if="totalDownloads > 0" class="wz-btn wz-btn--ghost wz-btn--sm" @click="clearAll">
          <Trash2 :size="13" />
          Réinitialiser
        </button>
      </div>

      <!-- Empty state -->
      <div v-if="totalDownloads === 0" class="empty">
        <div class="empty__icon">
          <BarChart3 :size="36" />
        </div>
        <h3 class="empty__title">Aucune donnée</h3>
        <p class="empty__sub">Tes statistiques apparaîtront après le premier téléchargement</p>
        <router-link to="/" class="wz-btn wz-btn--mint">
          <DownloadCloud :size="15" />
          Télécharger une vidéo
        </router-link>
      </div>

      <template v-else>

        <!-- ── KPIs ────────────────────────────────────────────────────── -->
        <div class="kpi-grid">
          <div class="kpi kpi--accent">
            <div class="kpi__icon"><DownloadCloud :size="18" /></div>
            <div class="kpi__val">{{ totalDownloads }}</div>
            <div class="kpi__label">Téléchargements</div>
          </div>
          <div class="kpi">
            <div class="kpi__icon"><Layers :size="18" /></div>
            <div class="kpi__val">{{ activePlatforms }}</div>
            <div class="kpi__label">Plateformes</div>
          </div>
          <div class="kpi">
            <div class="kpi__icon"><CalendarDays :size="18" /></div>
            <div class="kpi__val">{{ thisWeek }}</div>
            <div class="kpi__label">Cette semaine</div>
          </div>
          <div class="kpi">
            <div class="kpi__icon"><TrendingUp :size="18" /></div>
            <div class="kpi__val">{{ thisMonth }}</div>
            <div class="kpi__label">Ce mois</div>
          </div>
        </div>

        <!-- ── Platform breakdown ────────────────────────────────────────── -->
        <div class="section">
          <h2 class="section-title">
            <PieChart :size="15" />
            Par plateforme
          </h2>

          <div class="plat-list">
            <div v-for="p in platformStats" :key="p.id" class="plat-row">
              <div class="plat-row__info">
                <span :class="['plat-badge', `plat-badge--${p.id}`]">
                  <component :is="platformIcon(p.id)" :size="12" />
                </span>
                <span class="plat-name">{{ p.name }}</span>
                <span class="plat-pct">{{ p.pct }}%</span>
                <span class="plat-count">{{ p.count }} vidéo{{ p.count > 1 ? 's' : '' }}</span>
              </div>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{
                    width: p.pct + '%',
                    background: platformColor(p.id),
                  }"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Activity (last 7 days) ─────────────────────────────────── -->
        <div class="section">
          <h2 class="section-title">
            <Activity :size="15" />
            Activité — 7 derniers jours
          </h2>

          <div class="day-chart">
            <div v-for="d in weekActivity" :key="d.label" class="day-col">
              <div class="day-bar-wrap">
                <div
                  class="day-bar"
                  :style="{ height: d.heightPct + '%' }"
                  :title="`${d.count} téléchargement(s)`"
                ></div>
              </div>
              <span class="day-label">{{ d.label }}</span>
              <span class="day-count">{{ d.count || '' }}</span>
            </div>
          </div>
        </div>

        <!-- ── Recent downloads ───────────────────────────────────────── -->
        <div class="section">
          <h2 class="section-title">
            <Clock :size="15" />
            Récents
          </h2>

          <div class="recent-list">
            <div v-for="item in recentItems" :key="item.id" class="recent-item">

              <!-- Thumb -->
              <div class="recent-thumb">
                <img v-if="item.thumbnail" :src="item.thumbnail" :alt="item.title" />
                <div v-else class="recent-thumb__fb">
                  <component :is="platformIcon(item.platform)" :size="14" />
                </div>
                <span :class="['plat-dot', `plat-dot--${item.platform}`]"></span>
              </div>

              <!-- Info -->
              <div class="recent-info">
                <p class="recent-title">{{ item.title }}</p>
                <div class="recent-meta">
                  <span :class="['plat-chip', `plat-chip--${item.platform}`]">
                    <component :is="platformIcon(item.platform)" :size="9" />
                    {{ item.platform }}
                  </span>
                  <span class="recent-date">
                    <Clock :size="10" />
                    {{ fmtDate(item.date) }}
                  </span>
                </div>
              </div>

              <!-- Re-download -->
              <a
                v-if="item.url"
                :href="`/api/v1/download?url=${encodeURIComponent(item.url)}&filename=${encodeURIComponent((item.title || 'video') + '.mp4')}&platform=${item.platform}`"
                :download="(item.title || 'video') + '.mp4'"
                class="wz-btn wz-btn--ghost wz-btn--sm recent-dl"
                title="Re-télécharger"
              >
                <Download :size="13" />
              </a>

            </div>
          </div>
        </div>

      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  DownloadCloud, Trash2, Clock, Download, Layers,
  BarChart3, PieChart, Activity, TrendingUp, CalendarDays,
  Music2, Youtube, Pin, Facebook, Instagram, Linkedin, Twitter, Film,
} from 'lucide-vue-next'

// ─── Data ──────────────────────────────────────────────────────────────────
const items = ref([])

onMounted(() => {
  try {
    items.value = JSON.parse(localStorage.getItem('wzs_history') || '[]')
  } catch {
    items.value = []
  }
})

// ─── KPIs ───────────────────────────────────────────────────────────────────
const totalDownloads = computed(() => items.value.length)

const activePlatforms = computed(() =>
  new Set(items.value.map(i => i.platform).filter(Boolean)).size
)

const thisWeek = computed(() => {
  const cutoff = Date.now() - 7 * 86400000
  return items.value.filter(i => new Date(i.date).getTime() >= cutoff).length
})

const thisMonth = computed(() => {
  const cutoff = Date.now() - 30 * 86400000
  return items.value.filter(i => new Date(i.date).getTime() >= cutoff).length
})

// ─── Platform stats ──────────────────────────────────────────────────────────
const PLATFORM_NAMES = {
  tiktok: 'TikTok', youtube: 'YouTube', pinterest: 'Pinterest',
  facebook: 'Facebook', instagram: 'Instagram', linkedin: 'LinkedIn', twitter: 'Twitter/X',
}

const platformStats = computed(() => {
  const counts = {}
  items.value.forEach(i => {
    const p = i.platform || 'unknown'
    counts[p] = (counts[p] || 0) + 1
  })
  const total = totalDownloads.value || 1
  return Object.entries(counts)
    .map(([id, count]) => ({
      id,
      name: PLATFORM_NAMES[id] || id,
      count,
      pct: Math.round((count / total) * 100),
    }))
    .sort((a, b) => b.count - a.count)
})

// ─── Week activity chart (last 7 days) ───────────────────────────────────────
const weekActivity = computed(() => {
  const days = []
  const DAY_LABELS = ['Di', 'Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa']
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    d.setHours(0, 0, 0, 0)
    const next = new Date(d)
    next.setDate(next.getDate() + 1)
    const count = items.value.filter(item => {
      const t = new Date(item.date).getTime()
      return t >= d.getTime() && t < next.getTime()
    }).length
    days.push({ label: DAY_LABELS[d.getDay()], count })
  }
  const maxCount = Math.max(...days.map(d => d.count), 1)
  return days.map(d => ({
    ...d,
    heightPct: Math.round((d.count / maxCount) * 100),
  }))
})

// ─── Recent items (last 8) ────────────────────────────────────────────────────
const recentItems = computed(() => items.value.slice(0, 8))

// ─── Actions ─────────────────────────────────────────────────────────────────
const clearAll = () => {
  items.value = []
  localStorage.removeItem('wzs_history')
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
const platformIcon = (id) => ({
  tiktok: Music2, youtube: Youtube, pinterest: Pin,
  facebook: Facebook, instagram: Instagram, linkedin: Linkedin, twitter: Twitter,
}[id] || Film)

const platformColor = (id) => ({
  tiktok: '#ff2d55', youtube: '#ff0033', pinterest: '#e60023',
  facebook: '#1877f2', instagram: '#e1306c', linkedin: '#0a66c2', twitter: '#1da1f2',
}[id] || '#7a8499')

const fmtDate = (iso) => {
  const d = new Date(iso)
  const diff = Date.now() - d
  if (diff < 60000)    return 'À l\'instant'
  if (diff < 3600000)  return `Il y a ${Math.floor(diff / 60000)} min`
  if (diff < 86400000) return `Il y a ${Math.floor(diff / 3600000)} h`
  if (diff < 604800000) return `Il y a ${Math.floor(diff / 86400000)} j`
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
}
</script>

<style scoped>
.stats-page { padding: 36px 0 80px; }

/* ── Header ────────────────────────────────────────────────────────────────── */
.page-hd {
  display: flex; align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 12px;
}
.page-title {
  font-family: var(--font-display);
  font-size: 28px; font-weight: 800;
}
.page-sub { color: var(--text-md); font-size: 13.5px; margin-top: 3px; }

/* ── KPIs ──────────────────────────────────────────────────────────────────── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 28px;
}

.kpi {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color 0.18s var(--ease);
}
.kpi:hover { border-color: var(--border-md); }

.kpi--accent {
  background: linear-gradient(135deg, rgba(27,255,164,0.08) 0%, transparent 60%);
  border-color: rgba(27,255,164,0.2);
}
.kpi--accent:hover { border-color: rgba(27,255,164,0.35); }

.kpi__icon {
  color: var(--mint);
  opacity: 0.8;
}
.kpi__val {
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  color: var(--text-hi);
}
.kpi--accent .kpi__val { color: var(--mint); }
.kpi__label { font-size: 12px; color: var(--text-md); font-weight: 500; }

/* ── Section ───────────────────────────────────────────────────────────────── */
.section { margin-bottom: 28px; }
.section-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--text-hi);
  margin-bottom: 14px;
}
.section-title svg { color: var(--text-md); }

/* ── Platform bars ─────────────────────────────────────────────────────────── */
.plat-list {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
}

.plat-row {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.plat-row:last-child { border-bottom: none; }
.plat-row:hover { background: var(--bg-2); }

.plat-row__info {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 8px;
}

.plat-badge {
  width: 22px; height: 22px;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: #fff;
}
.plat-badge--tiktok    { background: #ff2d55; }
.plat-badge--youtube   { background: #ff0033; }
.plat-badge--pinterest { background: #e60023; }
.plat-badge--facebook  { background: #1877f2; }
.plat-badge--instagram { background: #e1306c; }
.plat-badge--linkedin  { background: #0a66c2; }
.plat-badge--twitter   { background: #1da1f2; }

.plat-name { font-size: 13.5px; font-weight: 600; flex: 1; }

.plat-pct {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-md);
  min-width: 32px;
  text-align: right;
}

.plat-count {
  font-size: 11px;
  color: var(--text-lo);
  min-width: 60px;
  text-align: right;
}

.bar-track {
  height: 4px;
  background: var(--bg-3);
  border-radius: 2px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.34, 1.1, 0.64, 1);
  min-width: 4px;
}

/* ── Day chart ─────────────────────────────────────────────────────────────── */
.day-chart {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 20px 16px 14px;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 120px;
}

.day-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
}

.day-bar-wrap {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.day-bar {
  width: 100%;
  max-width: 32px;
  background: var(--mint);
  border-radius: 3px 3px 0 0;
  min-height: 3px;
  opacity: 0.75;
  transition: opacity 0.15s;
}
.day-bar:hover { opacity: 1; }

.day-label {
  font-size: 10px;
  color: var(--text-lo);
  font-family: var(--font-mono);
}

.day-count {
  font-size: 10px;
  color: var(--text-md);
  font-weight: 600;
  min-height: 13px;
}

/* ── Recent list ────────────────────────────────────────────────────────────── */
.recent-list {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.recent-item:last-child { border-bottom: none; }
.recent-item:hover { background: var(--bg-2); }

.recent-thumb {
  position: relative;
  width: 52px; height: 40px;
  border-radius: var(--r-sm);
  overflow: hidden;
  background: var(--bg-2);
  flex-shrink: 0;
}
.recent-thumb img {
  width: 100%; height: 100%;
  object-fit: cover;
}
.recent-thumb__fb {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-lo);
}

.plat-dot {
  position: absolute;
  bottom: 2px; right: 2px;
  width: 8px; height: 8px;
  border-radius: 50%;
  border: 1.5px solid var(--bg-1);
}
.plat-dot--tiktok    { background: #ff2d55; }
.plat-dot--youtube   { background: #ff0033; }
.plat-dot--pinterest { background: #e60023; }
.plat-dot--facebook  { background: #1877f2; }
.plat-dot--instagram { background: #e1306c; }
.plat-dot--linkedin  { background: #0a66c2; }
.plat-dot--twitter   { background: #1da1f2; }

.recent-info { flex: 1; min-width: 0; }

.recent-title {
  font-size: 12.5px; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 4px;
}

.recent-meta {
  display: flex; align-items: center; gap: 7px;
}

.plat-chip {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 9px; font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  text-transform: capitalize;
  color: #fff;
}
.plat-chip--tiktok    { background: #ff2d55; }
.plat-chip--youtube   { background: #ff0033; }
.plat-chip--pinterest { background: #e60023; }
.plat-chip--facebook  { background: #1877f2; }
.plat-chip--instagram { background: #e1306c; }
.plat-chip--linkedin  { background: #0a66c2; }
.plat-chip--twitter   { background: #1da1f2; }

.recent-date {
  display: flex; align-items: center; gap: 3px;
  font-size: 10.5px; color: var(--text-lo);
}

.recent-dl { padding: 6px 10px; flex-shrink: 0; }

/* ── Empty ─────────────────────────────────────────────────────────────────── */
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

/* ── Responsive ────────────────────────────────────────────────────────────── */
@media (min-width: 480px) {
  .kpi-grid { grid-template-columns: repeat(4, 1fr); }
}
</style>
