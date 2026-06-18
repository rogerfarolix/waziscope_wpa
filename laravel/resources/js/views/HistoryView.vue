<template>
  <div class="stats-page">
    <div class="container">

      <!-- Header -->
      <div class="page-hd">
        <div class="page-hd__left">
          <div class="page-hd__icon">
            <BarChart3 :size="20" />
          </div>
          <div>
            <h1 class="page-title">Statistiques</h1>
            <p class="page-sub">Activité de téléchargement</p>
          </div>
        </div>
        <button v-if="totalDownloads > 0" class="wz-btn wz-btn--ghost wz-btn--sm" @click="clearAll">
          <Trash2 :size="13" />
          Réinitialiser
        </button>
      </div>

      <!-- Empty state -->
      <div v-if="totalDownloads === 0" class="empty">
        <div class="empty__ring">
          <BarChart3 :size="32" />
        </div>
        <h3 class="empty__title">Aucune donnée</h3>
        <p class="empty__sub">Lance ton premier téléchargement pour voir les stats ici</p>
        <router-link to="/" class="wz-btn wz-btn--mint">
          <DownloadCloud :size="15" />
          Télécharger une vidéo
        </router-link>
      </div>

      <template v-else>

        <!-- ── KPIs ────────────────────────────────────────────────────── -->
        <div class="kpi-grid">
          <div class="kpi kpi--accent">
            <div class="kpi__icon"><DownloadCloud :size="16" /></div>
            <div class="kpi__val">{{ totalDownloads }}</div>
            <div class="kpi__label">Total</div>
          </div>
          <div class="kpi">
            <div class="kpi__icon"><Layers :size="16" /></div>
            <div class="kpi__val">{{ activePlatforms }}</div>
            <div class="kpi__label">Plateformes</div>
          </div>
          <div class="kpi">
            <div class="kpi__icon"><CalendarDays :size="16" /></div>
            <div class="kpi__val">{{ thisWeek }}</div>
            <div class="kpi__label">Cette semaine</div>
          </div>
          <div class="kpi">
            <div class="kpi__icon"><TrendingUp :size="16" /></div>
            <div class="kpi__val">{{ thisMonth }}</div>
            <div class="kpi__label">Ce mois</div>
          </div>
        </div>

        <!-- ── Activity chart ─────────────────────────────────────────── -->
        <div class="section">
          <h2 class="section-title">
            <Activity :size="14" />
            Activité — 7 derniers jours
          </h2>

          <div class="day-chart">
            <div v-for="d in weekActivity" :key="d.label" class="day-col">
              <span class="day-count">{{ d.count || '' }}</span>
              <div class="day-bar-wrap">
                <div
                  class="day-bar"
                  :style="{ height: Math.max(d.heightPct, d.count ? 8 : 0) + '%' }"
                  :title="`${d.count} téléchargement(s)`"
                ></div>
              </div>
              <span class="day-label">{{ d.label }}</span>
            </div>
          </div>
        </div>

        <!-- ── Platform breakdown ─────────────────────────────────────── -->
        <div class="section">
          <h2 class="section-title">
            <PieChart :size="14" />
            Par plateforme
          </h2>

          <div class="plat-list">
            <div v-for="p in platformStats" :key="p.id" class="plat-row">
              <div class="plat-dot" :style="{ background: platformColor(p.id) }"></div>
              <span class="plat-name">{{ p.name }}</span>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ width: p.pct + '%', background: platformColor(p.id) }"
                ></div>
              </div>
              <span class="plat-count">{{ p.count }}</span>
              <span class="plat-pct">{{ p.pct }}%</span>
            </div>
          </div>
        </div>

        <!-- ── Top platform highlight ─────────────────────────────────── -->
        <div v-if="topPlatform" class="highlight-card">
          <div class="highlight-icon" :style="{ background: platformColor(topPlatform.id) + '22', color: platformColor(topPlatform.id) }">
            <component :is="platformIcon(topPlatform.id)" :size="22" />
          </div>
          <div class="highlight-body">
            <p class="highlight-label">Plateforme favorite</p>
            <p class="highlight-val">{{ topPlatform.name }}</p>
          </div>
          <div class="highlight-num">{{ topPlatform.count }} vidéo{{ topPlatform.count > 1 ? 's' : '' }}</div>
        </div>

      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  DownloadCloud, Trash2, Layers,
  BarChart3, PieChart, Activity, TrendingUp, CalendarDays,
  Music2, PlayCircle, Bookmark, Users, Camera, Briefcase, Bird, Film,
  Video, Tv2, Radio, MessageSquare, PlaySquare, Globe, Rss,
} from 'lucide-vue-next'

const items = ref([])

onMounted(() => {
  try { items.value = JSON.parse(localStorage.getItem('wzs_history') || '[]') }
  catch { items.value = [] }
})

// ─── KPIs ────────────────────────────────────────────────────────────────────
const totalDownloads  = computed(() => items.value.length)
const activePlatforms = computed(() => new Set(items.value.map(i => i.platform).filter(Boolean)).size)
const thisWeek  = computed(() => {
  const cut = Date.now() - 7 * 86400000
  return items.value.filter(i => new Date(i.date).getTime() >= cut).length
})
const thisMonth = computed(() => {
  const cut = Date.now() - 30 * 86400000
  return items.value.filter(i => new Date(i.date).getTime() >= cut).length
})

// ─── Platform stats ───────────────────────────────────────────────────────────
const PLATFORM_NAMES = {
  tiktok: 'TikTok',       youtube: 'YouTube',      pinterest: 'Pinterest',
  facebook: 'Facebook',   instagram: 'Instagram',  linkedin: 'LinkedIn',
  twitter: 'Twitter/X',   dailymotion: 'Dailymotion', vimeo: 'Vimeo',
  twitch: 'Twitch',       reddit: 'Reddit',        rumble: 'Rumble',
  odysee: 'Odysee',       snapchat: 'Snapchat',    bilibili: 'Bilibili',
}

const platformStats = computed(() => {
  const counts = {}
  items.value.forEach(i => { const p = i.platform || 'unknown'; counts[p] = (counts[p] || 0) + 1 })
  const total = totalDownloads.value || 1
  return Object.entries(counts)
    .map(([id, count]) => ({ id, name: PLATFORM_NAMES[id] || id, count, pct: Math.round((count / total) * 100) }))
    .sort((a, b) => b.count - a.count)
})

const topPlatform = computed(() => platformStats.value[0] || null)

// ─── Week chart ───────────────────────────────────────────────────────────────
const weekActivity = computed(() => {
  const DAY = ['Di', 'Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa']
  const days = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(); d.setDate(d.getDate() - i); d.setHours(0, 0, 0, 0)
    const next = new Date(d); next.setDate(next.getDate() + 1)
    const count = items.value.filter(item => {
      const t = new Date(item.date).getTime()
      return t >= d.getTime() && t < next.getTime()
    }).length
    days.push({ label: DAY[d.getDay()], count })
  }
  const mx = Math.max(...days.map(d => d.count), 1)
  return days.map(d => ({ ...d, heightPct: Math.round((d.count / mx) * 100) }))
})

// ─── Helpers ─────────────────────────────────────────────────────────────────
const platformIcon = (id) => ({
  tiktok: Music2,        youtube: PlayCircle,  pinterest: Bookmark,
  facebook: Users,       instagram: Camera,    linkedin: Briefcase, twitter: Bird,
  dailymotion: Video,    vimeo: Tv2,           twitch: Radio,
  reddit: MessageSquare, rumble: PlaySquare,   odysee: Globe,
  snapchat: Rss,         bilibili: Film,
}[id] || Film)

const platformColor = (id) => ({
  tiktok: '#ff2d55',      youtube: '#ff0033',    pinterest: '#e60023',
  facebook: '#1877f2',    instagram: '#e1306c',  linkedin: '#0a66c2',
  twitter: '#1da1f2',     dailymotion: '#0096e6', vimeo: '#1ab7ea',
  twitch: '#9146ff',      reddit: '#ff4500',     rumble: '#85c742',
  odysee: '#e04040',      snapchat: '#f5d020',   bilibili: '#fb7299',
}[id] || '#3a4155')

const clearAll = () => { items.value = []; localStorage.removeItem('wzs_history') }
</script>

<style scoped>
.stats-page { padding: 36px 0 80px; }

/* ── Header ────────────────────────────────────────────────────────────────── */
.page-hd {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 28px;
}
.page-hd__left { display: flex; align-items: center; gap: 14px; }
.page-hd__icon {
  width: 44px; height: 44px;
  background: var(--mint-dim); border: 1px solid rgba(27,255,164,0.2);
  border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center;
  color: var(--mint); flex-shrink: 0;
}
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; }
.page-sub   { color: var(--text-md); font-size: 13px; margin-top: 1px; }

/* ── KPIs ──────────────────────────────────────────────────────────────────── */
.kpi-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 10px; margin-bottom: 24px;
}
.kpi {
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--r-lg); padding: 20px 16px;
  display: flex; flex-direction: column; gap: 8px;
  transition: border-color 0.2s;
}
.kpi:hover { border-color: var(--border-md); }
.kpi--accent {
  background: linear-gradient(135deg, rgba(27,255,164,0.08) 0%, transparent 70%);
  border-color: rgba(27,255,164,0.2);
}
.kpi--accent:hover { border-color: rgba(27,255,164,0.35); }

.kpi__icon { color: var(--mint); opacity: 0.85; }
.kpi__val  {
  font-family: var(--font-display); font-size: 42px; font-weight: 800;
  line-height: 1; color: var(--text-hi); letter-spacing: -1px;
}
.kpi--accent .kpi__val { color: var(--mint); }
.kpi__label { font-size: 11.5px; font-weight: 500; color: var(--text-md); text-transform: uppercase; letter-spacing: 0.5px; }

/* ── Section ───────────────────────────────────────────────────────────────── */
.section { margin-bottom: 20px; }
.section-title {
  display: flex; align-items: center; gap: 7px;
  font-family: var(--font-display); font-size: 13.5px; font-weight: 700;
  color: var(--text-md); text-transform: uppercase; letter-spacing: 0.5px;
  margin-bottom: 12px;
}
.section-title svg { opacity: 0.6; }

/* ── Day chart ─────────────────────────────────────────────────────────────── */
.day-chart {
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--r-lg); padding: 20px 20px 14px;
  display: flex; align-items: flex-end; gap: 8px;
  height: 140px;
}
.day-col {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; gap: 5px; height: 100%;
}
.day-count {
  font-size: 11px; font-weight: 700; color: var(--mint);
  min-height: 16px; font-family: var(--font-mono);
}
.day-bar-wrap {
  flex: 1; width: 100%; display: flex; align-items: flex-end; justify-content: center;
}
.day-bar {
  width: 100%; max-width: 36px;
  background: linear-gradient(180deg, var(--mint) 0%, rgba(27,255,164,0.4) 100%);
  border-radius: 4px 4px 2px 2px; min-height: 0;
  transition: height 0.4s cubic-bezier(0.34,1.2,0.64,1), opacity 0.15s;
  opacity: 0.8;
}
.day-bar:hover { opacity: 1; }
.day-label {
  font-size: 10.5px; color: var(--text-lo);
  font-family: var(--font-mono); font-weight: 500;
}

/* ── Platform bars ─────────────────────────────────────────────────────────── */
.plat-list {
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--r-lg); overflow: hidden;
}
.plat-row {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 18px; border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.plat-row:last-child { border: none; }
.plat-row:hover { background: var(--bg-2); }

.plat-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.plat-name { font-size: 13.5px; font-weight: 600; min-width: 90px; }

.bar-track {
  flex: 1; height: 5px; background: var(--bg-3);
  border-radius: 3px; overflow: hidden;
}
.bar-fill {
  height: 100%; border-radius: 3px; min-width: 4px;
  transition: width 0.5s cubic-bezier(0.34,1.1,0.64,1);
  opacity: 0.8;
}
.plat-row:hover .bar-fill { opacity: 1; }

.plat-count {
  font-family: var(--font-mono); font-size: 13px; font-weight: 700;
  color: var(--text-hi); min-width: 24px; text-align: right;
}
.plat-pct {
  font-size: 11px; color: var(--text-md); min-width: 32px; text-align: right;
  font-family: var(--font-mono);
}

/* ── Highlight card ────────────────────────────────────────────────────────── */
.highlight-card {
  display: flex; align-items: center; gap: 16px;
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--r-lg); padding: 18px 20px;
  transition: border-color 0.2s;
}
.highlight-card:hover { border-color: var(--border-md); }
.highlight-icon {
  width: 48px; height: 48px; border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.highlight-body { flex: 1; }
.highlight-label { font-size: 11px; color: var(--text-md); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }
.highlight-val   { font-family: var(--font-display); font-size: 18px; font-weight: 800; margin-top: 2px; }
.highlight-num   { font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--text-md); }

/* ── Empty ─────────────────────────────────────────────────────────────────── */
.empty {
  text-align: center; padding: 80px 20px;
  display: flex; flex-direction: column; align-items: center; gap: 14px;
}
.empty__ring {
  width: 80px; height: 80px;
  border: 2px solid var(--border-md); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-lo); margin-bottom: 6px;
}
.empty__title { font-family: var(--font-display); font-size: 20px; font-weight: 700; }
.empty__sub   { color: var(--text-md); font-size: 14px; max-width: 280px; line-height: 1.55; }

/* ── Responsive ────────────────────────────────────────────────────────────── */
@media (max-width: 560px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .plat-name { min-width: 70px; }
}
</style>
