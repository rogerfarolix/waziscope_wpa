<template>
  <div class="home">

    <!-- ── Hero compact ──────────────────────────────────────────────────── -->
    <section class="hero">
      <div class="hero__bg" aria-hidden="true">
        <div class="blob blob--a"></div>
        <div class="blob blob--b"></div>
        <div class="grid-lines"></div>
      </div>

      <div class="container hero__inner">
        <div class="hero__badge">
          <span class="badge-dot"></span>
          16 plateformes supportées
        </div>

        <h1 class="hero__h1">
          Télécharge n'importe<br>
          quelle <em>vidéo</em>
        </h1>

        <p class="hero__sub">
          TikTok sans watermark · YouTube 4K · Playlists · Longs métrages · Audio MP3
        </p>
      </div>
    </section>

    <!-- ── Extractor ─────────────────────────────────────────────────────── -->
    <section class="extractor">
      <div class="container">

        <!-- Platform bar — spans full width above the 2-col grid -->
        <div class="plat-bar">
          <button
            v-for="p in platforms"
            :key="p.id"
            :class="['plat-chip', `plat-chip--${p.id}`, { 'plat-chip--on': detectedPlatform === p.id }]"
            @click="detectedPlatform = p.id"
            :title="p.name"
          >
            <component :is="platformIcon(p.id)" :size="13" />
            <span>{{ p.name }}</span>
            <span v-if="p.no_watermark" class="nowm-dot"></span>
          </button>
        </div>

        <!-- 2-col grid: left=controls, right=result -->
        <div class="extractor-grid">

          <!-- ── Left col: controls ──────────────────────────────────────── -->
          <div class="col-left">

            <!-- Mode tabs -->
            <div class="tabs">
              <button :class="['tab', { 'tab--on': mode === 'single' }]"   @click="mode = 'single'">
                <Film :size="14" /> Vidéo unique
              </button>
              <button :class="['tab', { 'tab--on': mode === 'playlist' }]" @click="mode = 'playlist'">
                <List :size="14" /> Playlist
              </button>
            </div>

            <!-- Input card -->
            <div class="input-card">
              <div :class="['input-wrap', { 'input-wrap--focus': focused }]">
                <Link2 :size="16" class="input-icon" />
                <input
                  v-model="inputUrl"
                  ref="inputEl"
                  type="url"
                  :placeholder="mode === 'playlist' ? 'URL playlist YouTube, Vimeo…' : 'Colle le lien de la vidéo…'"
                  class="url-input"
                  autocomplete="off" autocorrect="off" spellcheck="false"
                  @focus="focused = true" @blur="focused = false"
                  @keydown.enter="doAction"
                  :disabled="loading"
                />
                <button v-if="inputUrl" class="clear-btn" @click="clearInput">
                  <X :size="14" />
                </button>
                <button class="paste-btn" @click="pasteFromClipboard" title="Coller">
                  <Clipboard :size="14" />
                </button>
              </div>

              <!-- Options row -->
              <div class="options-row">
                <template v-if="mode === 'single'">
                  <span class="opt-label">Qualité</span>
                  <div class="opt-btns">
                    <button
                      v-for="q in qualities" :key="q.id"
                      :class="['opt-btn', { 'opt-btn--on': selectedQuality === q.id }]"
                      @click="selectedQuality = q.id"
                    >{{ q.label }}</button>
                  </div>
                </template>
                <template v-else>
                  <span class="opt-label">Limite</span>
                  <div class="opt-btns">
                    <button
                      v-for="n in [10, 20, 30, 50]" :key="n"
                      :class="['opt-btn', { 'opt-btn--on': playlistLimit === n }]"
                      @click="playlistLimit = n"
                    >{{ n }}</button>
                  </div>
                </template>

                <button
                  class="go-btn"
                  :disabled="!inputUrl.trim() || loading"
                  @click="doAction"
                >
                  <Loader2 v-if="loading" :size="16" class="spin" />
                  <DownloadCloud v-else :size="16" />
                  {{ loading ? 'Analyse…' : mode === 'playlist' ? 'Charger' : 'Extraire' }}
                </button>
              </div>
            </div>

            <!-- Loading (left col) -->
            <div v-if="loading" class="loading-card">
              <div class="loading-bar"><div class="loading-fill"></div></div>
              <p class="loading-txt">Extraction en cours…</p>
            </div>

            <!-- Error (left col) -->
            <transition name="fade-up">
              <div v-if="errorMsg" class="error-bar">
                <AlertCircle :size="15" />
                <span>{{ errorMsg }}</span>
                <button @click="errorMsg = null"><X :size="13" /></button>
              </div>
            </transition>

            <!-- Empty state when no result yet -->
            <div v-if="!loading && !result && !playlist && !errorMsg" class="empty-hint">
              <div class="empty-hint__ring">
                <DownloadCloud :size="28" />
              </div>
              <p>Colle une URL ci-dessus<br>pour lancer l'extraction</p>
            </div>

          </div>

          <!-- ── Right col: result / playlist ───────────────────────────── -->
          <div class="col-right">

            <!-- Result card -->
            <transition name="fade-up">
              <div v-if="result && !loading" class="result-card">

                <div v-if="result.thumbnail" class="result-thumb">
                  <img :src="result.thumbnail" :alt="result.title" loading="lazy" />
                  <div class="result-thumb__overlay">
                    <span class="plat-tag" :data-plat="result.platform">{{ result.platform }}</span>
                    <span v-if="result.duration" class="dur-tag">
                      <Clock :size="9" /> {{ fmtDuration(result.duration) }}
                    </span>
                  </div>
                </div>

                <div class="result-info">
                  <div class="result-top">
                    <div>
                      <h3 class="result-title">{{ result.title }}</h3>
                      <p v-if="result.author" class="result-author">
                        <UserRound :size="12" /> {{ result.author }}
                      </p>
                    </div>
                    <div v-if="result.view_count || result.like_count" class="result-stats">
                      <span v-if="result.view_count" class="stat-pill">
                        <Eye :size="11" /> {{ fmtCount(result.view_count) }}
                      </span>
                      <span v-if="result.like_count" class="stat-pill">
                        <Heart :size="11" /> {{ fmtCount(result.like_count) }}
                      </span>
                    </div>
                  </div>

                  <div v-if="result.platform === 'tiktok'" class="nowm-badge">
                    <ShieldCheck :size="13" /> Sans watermark
                  </div>

                  <div class="actions">
                    <a
                      :href="result.proxy_download_url || dlUrl(result.no_watermark_url || result.best_url, result.title)"
                      :download="safe(result.title) + '.mp4'"
                      class="action-primary"
                      @click="onDl(result)"
                    >
                      <DownloadCloud :size="15" />
                      Télécharger{{ result.platform === 'tiktok' ? ' sans WM' : '' }}
                    </a>

                    <div class="action-row">
                      <a
                        v-if="ffmpeg && (result.proxy_strip_url || stripUrl(result))"
                        :href="result.proxy_strip_url || stripUrl(result)"
                        :download="safe(result.title) + '_clean.mp4'"
                        class="action-sec"
                        title="Sans métadonnées"
                        @click="onDl(result)"
                      >
                        <ShieldOff :size="13" /> Sans métadonnées
                      </a>
                      <a
                        v-if="result.audio_only_url"
                        :href="dlUrl(result.audio_only_url, result.title + '_audio')"
                        :download="safe(result.title) + '.mp3'"
                        class="action-sec"
                      >
                        <Music :size="13" /> Audio MP3
                      </a>
                    </div>
                  </div>

                  <div v-if="result.formats?.length > 1" class="formats-wrap">
                    <button class="formats-toggle" @click="showFmts = !showFmts">
                      <Layers :size="12" />
                      {{ result.formats.length }} formats
                      <ChevronDown :size="12" :class="{ flip: showFmts }" />
                    </button>
                    <transition name="drop">
                      <div v-if="showFmts" class="formats-list">
                        <a
                          v-for="fmt in [...result.formats].reverse()"
                          :key="fmt.format_id"
                          :href="fmt.proxy_url || dlUrl(fmt.url, result.title)"
                          :download="`${safe(result.title)}_${fmt.quality || fmt.format_id}.${fmt.ext}`"
                          class="fmt-item"
                        >
                          <span class="fmt-q">{{ fmt.height ? fmt.height + 'p' : fmt.quality }}</span>
                          <span class="fmt-ext">{{ fmt.ext }}</span>
                          <span v-if="fmt.filesize" class="fmt-sz">{{ fmtSize(fmt.filesize) }}</span>
                          <span v-if="fmt.no_watermark" class="fmt-wm">No WM</span>
                          <Download :size="12" class="fmt-dl" />
                        </a>
                      </div>
                    </transition>
                  </div>
                </div>
              </div>
            </transition>

            <!-- Playlist card -->
            <transition name="fade-up">
              <div v-if="playlist && !loading" class="playlist-card">
                <div class="playlist-head">
                  <div class="playlist-head__info">
                    <List :size="15" class="playlist-icon" />
                    <div>
                      <p class="playlist-title">{{ playlist.playlist_title }}</p>
                      <p class="playlist-sub">{{ playlist.items.filter(i => i.success).length }} / {{ playlist.items.length }} extraites</p>
                    </div>
                  </div>
                  <button class="action-primary action-primary--sm" @click="dlAll">
                    <DownloadCloud :size="14" /> Tout télécharger
                  </button>
                </div>

                <div class="playlist-items">
                  <div
                    v-for="item in playlist.items"
                    :key="item.index"
                    :class="['pl-row', { 'pl-row--err': !item.success }]"
                  >
                    <span class="pl-num">{{ item.index + 1 }}</span>
                    <div class="pl-info">
                      <p class="pl-title">{{ item.data?.title || item.error || '—' }}</p>
                      <p v-if="item.data?.duration || item.data?.author" class="pl-meta">
                        <span v-if="item.data?.author">{{ item.data.author }}</span>
                        <span v-if="item.data?.duration"> · {{ fmtDuration(item.data.duration) }}</span>
                      </p>
                    </div>
                    <a
                      v-if="item.success && item.data"
                      :href="item.data.proxy_download_url || dlUrl(item.data.no_watermark_url || item.data.best_url, item.data.title)"
                      :download="safe(item.data.title) + '.mp4'"
                      class="pl-dl"
                      @click="onDl(item.data)"
                    ><Download :size="14" /></a>
                    <AlertCircle v-else :size="14" class="pl-err" />
                  </div>
                </div>
              </div>
            </transition>

          </div>
        </div><!-- /extractor-grid -->
      </div>
    </section>

    <!-- ── Footer info ────────────────────────────────────────────────────── -->
    <section class="info-section">
      <div class="container">
        <div class="info-grid">
          <div v-for="f in features" :key="f.title" class="info-card">
            <div class="info-icon">
              <component :is="f.icon" :size="18" />
            </div>
            <h4 class="info-title">{{ f.title }}</h4>
            <p class="info-desc">{{ f.desc }}</p>
          </div>
        </div>
      </div>
    </section>

  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import {
  DownloadCloud, Link2, X, Loader2, Clock, Music, Layers, ChevronDown,
  Download, AlertCircle, ShieldCheck, ShieldOff, UserRound, Eye, Heart,
  Zap, Clipboard, Film, List,
  PlayCircle, Bookmark, Users, Camera, Briefcase, Bird,
  Video, Tv2, Radio, MessageSquare, PlaySquare, Globe, Rss, Music2,
} from 'lucide-vue-next'

const route  = useRoute()
const notify = inject('notify')

// ─── State ───────────────────────────────────────────────────────────────────
const inputUrl        = ref('')
const inputEl         = ref(null)
const focused         = ref(false)
const loading         = ref(false)
const result          = ref(null)
const playlist        = ref(null)
const errorMsg        = ref(null)
const showFmts        = ref(false)
const detectedPlatform = ref(null)
const ffmpeg          = ref(false)
const mode            = ref('single')
const selectedQuality = ref('best')
const playlistLimit   = ref(20)

const qualities = [
  { id: 'best',  label: 'Auto' },
  { id: '4k',    label: '4K' },
  { id: '1080',  label: '1080p' },
  { id: '720',   label: '720p' },
  { id: '480',   label: '480p' },
  { id: 'audio', label: 'Audio' },
]

// ─── Platforms ───────────────────────────────────────────────────────────────
const platforms = ref([
  { id: 'tiktok',      name: 'TikTok',       no_watermark: true  },
  { id: 'youtube',     name: 'YouTube',       no_watermark: false },
  { id: 'instagram',   name: 'Instagram',     no_watermark: false },
  { id: 'facebook',    name: 'Facebook',      no_watermark: false },
  { id: 'twitter',     name: 'Twitter/X',     no_watermark: false },
  { id: 'pinterest',   name: 'Pinterest',     no_watermark: false },
  { id: 'linkedin',    name: 'LinkedIn',      no_watermark: false },
  { id: 'vimeo',       name: 'Vimeo',         no_watermark: false },
  { id: 'dailymotion', name: 'Dailymotion',   no_watermark: false },
  { id: 'twitch',      name: 'Twitch',        no_watermark: false },
  { id: 'reddit',      name: 'Reddit',        no_watermark: false },
  { id: 'rumble',      name: 'Rumble',        no_watermark: false },
  { id: 'odysee',      name: 'Odysee',        no_watermark: false },
  { id: 'snapchat',    name: 'Snapchat',      no_watermark: false },
  { id: 'bilibili',    name: 'Bilibili',      no_watermark: false },
])

const platformIcon = (id) => ({
  tiktok: Music2,        youtube: PlayCircle,  pinterest: Bookmark,
  facebook: Users,       instagram: Camera,    linkedin: Briefcase,
  twitter: Bird,         dailymotion: Video,   vimeo: Tv2,
  twitch: Radio,         reddit: MessageSquare, rumble: PlaySquare,
  odysee: Globe,         snapchat: Rss,        bilibili: Film,
}[id] || Film)

const features = [
  { icon: Film,        title: 'Longs métrages',      desc: 'Films, documentaires, conférences — aucune limite de durée.' },
  { icon: List,        title: 'Playlists entières',   desc: 'YouTube, Vimeo et autres — jusqu\'à 50 vidéos d\'un coup.' },
  { icon: ShieldCheck, title: 'TikTok sans watermark', desc: 'Via l\'API mobile officielle, propre et sans logo.' },
  { icon: ShieldOff,   title: 'Suppression métadonnées', desc: 'GPS, dates, auteur effacés — sans re-encodage.' },
  { icon: Music,       title: 'Audio MP3',            desc: 'Extrait uniquement la piste audio depuis n\'importe quelle vidéo.' },
  { icon: Zap,         title: '16 plateformes',       desc: 'TikTok, YouTube, Reddit, Twitch, Vimeo, Bilibili et plus encore.' },
]

// ─── Mount ───────────────────────────────────────────────────────────────────
onMounted(async () => {
  const shared = route.query.url || route.query.shared
  if (shared) { inputUrl.value = decodeURIComponent(String(shared)); doAction(); return }

  window.addEventListener('wzs:share', e => { inputUrl.value = e.detail.url; doAction() })

  try {
    const [platRes, capRes] = await Promise.all([
      axios.get('/api/v1/platforms').catch(() => null),
      axios.get('/api/v1/capabilities').catch(() => null),
    ])
    if (platRes?.data?.platforms) platforms.value = platRes.data.platforms
    if (capRes?.data?.ffmpeg !== undefined) ffmpeg.value = capRes.data.ffmpeg
  } catch {}
})

// ─── Helpers ─────────────────────────────────────────────────────────────────
const detect = (url) => {
  const u = url.toLowerCase()
  const map = [
    ['tiktok',['tiktok']], ['youtube',['youtu']], ['pinterest',['pin.it','pinterest']],
    ['facebook',['facebook','fb.']], ['instagram',['instagram']], ['linkedin',['linkedin']],
    ['twitter',['twitter','x.com','t.co']], ['dailymotion',['dailymotion','dai.ly']],
    ['vimeo',['vimeo']], ['twitch',['twitch']], ['reddit',['reddit','redd.it']],
    ['rumble',['rumble']], ['odysee',['odysee','lbry']], ['snapchat',['snapchat']],
    ['bilibili',['bilibili','b23.tv']],
  ]
  for (const [id, pats] of map) {
    if (pats.some(p => u.includes(p))) {
      detectedPlatform.value = id
      if (id === 'youtube' && u.includes('list=')) mode.value = 'playlist'
      return
    }
  }
  detectedPlatform.value = null
}

const clearInput = () => {
  inputUrl.value = ''; detectedPlatform.value = null
  result.value = null; playlist.value = null; errorMsg.value = null
  inputEl.value?.focus()
}

const pasteFromClipboard = async () => {
  try {
    const t = await navigator.clipboard.readText()
    if (t?.startsWith('http')) { inputUrl.value = t.trim(); detect(t) }
  } catch { notify({ message: 'Presse-papiers refusé', type: 'warning' }) }
}

const doAction = () => mode.value === 'playlist' ? doPlaylist() : doExtract()

// ─── Extract ─────────────────────────────────────────────────────────────────
const doExtract = async () => {
  const url = inputUrl.value.trim(); if (!url) return
  detect(url); loading.value = true; result.value = null; playlist.value = null
  errorMsg.value = null; showFmts.value = false

  try {
    const res = await axios.post('/api/v1/extract', { url, quality: selectedQuality.value })
    if (!res.data.success) { errorMsg.value = res.data.message || 'Extraction échouée'; return }
    result.value = res.data.data
    if (res.data.ffmpeg_available !== undefined) ffmpeg.value = res.data.ffmpeg_available
    notify({ message: 'Vidéo trouvée !', type: 'success' })
  } catch (e) {
    errorMsg.value = e.response?.data?.message || 'Erreur serveur'
    notify({ message: errorMsg.value, type: 'danger' })
  } finally { loading.value = false }
}

// ─── Playlist ────────────────────────────────────────────────────────────────
const doPlaylist = async () => {
  const url = inputUrl.value.trim(); if (!url) return
  detect(url); loading.value = true; result.value = null; playlist.value = null; errorMsg.value = null

  try {
    const res = await axios.post('/api/v1/extract/playlist', { url, limit: playlistLimit.value })
    if (!res.data.success) { errorMsg.value = res.data.message || 'Playlist échouée'; return }
    playlist.value = res.data
    notify({ message: `${res.data.items.filter(i => i.success).length} vidéos extraites`, type: 'success' })
  } catch (e) {
    errorMsg.value = e.response?.data?.message || 'Erreur playlist'
    notify({ message: errorMsg.value, type: 'danger' })
  } finally { loading.value = false }
}

const dlAll = () => {
  if (!playlist.value) return
  playlist.value.items.filter(i => i.success && i.data).forEach((item, idx) => {
    setTimeout(() => {
      const a = document.createElement('a')
      a.href = item.data.proxy_download_url || dlUrl(item.data.no_watermark_url || item.data.best_url, item.data.title)
      a.download = safe(item.data.title) + '.mp4'
      a.click(); onDl(item.data)
    }, idx * 800)
  })
}

// ─── URL / history helpers ────────────────────────────────────────────────────
const dlUrl = (url, title) =>
  url ? `/api/v1/download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(safe(title) + '.mp4')}` : '#'

const stripUrl = (v) => {
  const u = v?.no_watermark_url || v?.best_url; if (!u) return '#'
  return `/api/v1/strip?url=${encodeURIComponent(u)}&filename=${encodeURIComponent(safe(v.title))}&platform=${v.platform}`
}

const onDl = (v) => {
  try {
    const h = JSON.parse(localStorage.getItem('wzs_history') || '[]')
    h.unshift({ id: Date.now(), title: v.title, thumbnail: v.thumbnail, platform: v.platform, url: v.best_url, date: new Date().toISOString() })
    localStorage.setItem('wzs_history', JSON.stringify(h.slice(0, 100)))
  } catch {}
  notify({ message: 'Téléchargement lancé !', type: 'success' })
}

const safe    = s => (s || 'video').replace(/[^\w\-. ]/g, '_').substring(0, 80)
const fmtSize = b => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`
const fmtCount = n => n >= 1e9 ? (n/1e9).toFixed(1)+'G' : n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n)
const fmtDuration = s => {
  if (!s) return ''
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60)
  return h > 0 ? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}` : `${m}:${String(sec).padStart(2,'0')}`
}
</script>

<style scoped>
/* ── Hero ─────────────────────────────────────────────────────────────────── */
.hero {
  position: relative; padding: 64px 0 48px; overflow: hidden;
}
.hero__bg { position: absolute; inset: 0; }
.blob {
  position: absolute; border-radius: 50%; filter: blur(100px); pointer-events: none;
}
.blob--a {
  width: 500px; height: 400px;
  background: radial-gradient(circle, rgba(27,255,164,0.15) 0%, transparent 65%);
  top: -140px; left: -100px;
  animation: drift 11s ease-in-out infinite;
}
.blob--b {
  width: 350px; height: 350px;
  background: radial-gradient(circle, rgba(145,70,255,0.1) 0%, transparent 65%);
  top: -80px; right: -60px;
  animation: drift 14s ease-in-out infinite reverse;
}
@keyframes drift { 0%,100% { transform: translate(0,0); } 50% { transform: translate(16px,-20px); } }
.grid-lines {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.022) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.022) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: linear-gradient(to bottom, transparent, rgba(0,0,0,0.5) 40%, rgba(0,0,0,0.5) 60%, transparent);
}
.hero__inner {
  position: relative; z-index: 1;
  display: flex; flex-direction: column; align-items: flex-start;
}

.hero__badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 14px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border-md);
  border-radius: 20px;
  font-size: 12px; font-family: var(--font-mono); color: var(--text-md);
  margin-bottom: 20px;
}
.badge-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--mint);
  box-shadow: 0 0 8px var(--mint); animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

.hero__h1 {
  font-family: var(--font-display);
  font-size: clamp(36px, 8vw, 62px);
  font-weight: 800; line-height: 1.08;
  letter-spacing: -1.5px; margin-bottom: 16px;
}
.hero__h1 em { font-style: normal; color: var(--mint); }

.hero__sub {
  font-size: 14.5px; color: var(--text-md); line-height: 1.6;
  font-family: var(--font-mono);
}

/* ── Extractor ────────────────────────────────────────────────────────────── */
.extractor { padding: 0 0 60px; }

/* 2-col grid */
.extractor-grid {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 20px;
  align-items: start;
}
.col-left  { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.col-right { display: flex; flex-direction: column; gap: 12px; min-width: 0; }

/* Empty hint (right col placeholder) */
.empty-hint {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; padding: 60px 20px;
  border: 1px dashed var(--border-md); border-radius: var(--r-xl);
  color: var(--text-lo); text-align: center;
}
.empty-hint__ring {
  width: 64px; height: 64px; border-radius: 50%;
  background: var(--bg-1); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center; color: var(--text-lo);
}
.empty-hint p { font-size: 13px; line-height: 1.6; color: var(--text-lo); }

/* Platform bar — horizontal scroll */
.plat-bar {
  display: flex; gap: 5px; overflow-x: auto; padding-bottom: 4px;
  margin-bottom: 12px; scrollbar-width: none;
}
.plat-bar::-webkit-scrollbar { display: none; }
.plat-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: 20px; cursor: pointer;
  font-size: 12px; font-weight: 500; color: var(--text-md);
  white-space: nowrap; flex-shrink: 0;
  transition: all 0.15s; position: relative;
}
.plat-chip:hover { color: var(--text-hi); border-color: var(--border-md); }
.plat-chip--on  { background: var(--bg-2); border-color: var(--border-hi); color: var(--text-hi); }
.nowm-dot {
  width: 5px; height: 5px; border-radius: 50%; background: var(--mint);
  box-shadow: 0 0 5px var(--mint);
}

/* Mode tabs */
.tabs { display: flex; gap: 0; margin-bottom: 10px; }
.tab {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 16px; background: var(--bg-1); border: 1px solid var(--border);
  font-family: var(--font-body); font-size: 13px; font-weight: 500;
  color: var(--text-md); cursor: pointer; transition: all 0.15s;
}
.tab:first-child { border-radius: var(--r-sm) 0 0 var(--r-sm); }
.tab:last-child  { border-radius: 0 var(--r-sm) var(--r-sm) 0; margin-left: -1px; }
.tab--on { background: var(--bg-2); color: var(--text-hi); border-color: var(--border-hi); z-index: 1; }

/* Input card */
.input-card {
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--r-xl); padding: 14px 16px;
  transition: border-color 0.2s;
}
.input-card:focus-within { border-color: var(--border-hi); }

.input-wrap {
  display: flex; align-items: center; gap: 8px;
  background: var(--bg); border: 1px solid var(--border-md);
  border-radius: var(--r-md); padding: 10px 12px;
  transition: border-color 0.18s, box-shadow 0.18s;
}
.input-wrap--focus { border-color: var(--mint); box-shadow: 0 0 0 3px var(--mint-glow); }
.input-icon { color: var(--text-lo); flex-shrink: 0; }
.url-input {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text-hi); font-family: var(--font-mono); font-size: 13px; min-width: 0;
}
.url-input::placeholder { color: var(--text-lo); }
.clear-btn, .paste-btn {
  background: none; border: none; color: var(--text-lo); cursor: pointer;
  padding: 3px; border-radius: 4px; display: flex; flex-shrink: 0;
  transition: all 0.15s;
}
.clear-btn:hover, .paste-btn:hover { background: var(--bg-2); color: var(--text-hi); }

/* Options row */
.options-row {
  display: flex; align-items: center; gap: 10px; margin-top: 12px; flex-wrap: wrap;
}
.opt-label { font-size: 11.5px; font-weight: 500; color: var(--text-md); white-space: nowrap; }
.opt-btns  { display: flex; gap: 4px; flex: 1; flex-wrap: wrap; }
.opt-btn {
  padding: 4px 10px;
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--r-sm); font-size: 12px; font-weight: 500;
  color: var(--text-md); cursor: pointer; transition: all 0.15s;
}
.opt-btn--on { background: var(--mint-dim); border-color: rgba(27,255,164,0.35); color: var(--mint); }
.opt-btn:hover:not(.opt-btn--on) { color: var(--text-hi); border-color: var(--border-md); }

.go-btn {
  display: flex; align-items: center; gap: 7px;
  padding: 9px 20px; background: var(--mint); color: #000;
  border: none; border-radius: var(--r-md);
  font-family: var(--font-body); font-size: 14px; font-weight: 700;
  cursor: pointer; white-space: nowrap; flex-shrink: 0;
  transition: opacity 0.15s, transform 0.15s;
}
.go-btn:hover:not(:disabled) { opacity: 0.88; transform: translateY(-1px); }
.go-btn:disabled { opacity: 0.35; cursor: not-allowed; }

/* Loading */
.loading-card {
  margin-top: 14px;
  background: var(--bg-1); border: 1px solid var(--border); border-radius: var(--r-lg);
  padding: 20px; display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.loading-bar {
  width: 100%; max-width: 280px; height: 3px;
  background: var(--bg-3); border-radius: 2px; overflow: hidden;
}
.loading-fill {
  height: 100%; border-radius: 2px; background: var(--mint);
  animation: indeterminate 1.4s ease-in-out infinite;
  width: 40%;
}
@keyframes indeterminate {
  0%   { transform: translateX(-150%); }
  100% { transform: translateX(350%); }
}
.loading-txt { font-size: 13px; color: var(--text-md); font-family: var(--font-mono); }

/* ── Result card ──────────────────────────────────────────────────────────── */
.result-card {
  margin-top: 14px;
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--r-xl); overflow: hidden;
}

.result-thumb {
  position: relative; width: 100%; height: 200px;
  background: var(--bg-2); overflow: hidden;
}
.result-thumb img {
  width: 100%; height: 100%; object-fit: cover; display: block;
  filter: brightness(0.9);
}
.result-thumb__overlay {
  position: absolute; inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 60%);
  display: flex; align-items: flex-end; justify-content: space-between;
  padding: 12px 14px;
}
.plat-tag {
  padding: 3px 9px; border-radius: 5px;
  font-size: 11px; font-weight: 700; text-transform: capitalize;
  background: rgba(0,0,0,0.6); color: #fff; backdrop-filter: blur(6px);
  border: 1px solid rgba(255,255,255,0.15);
}
.dur-tag {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; font-family: var(--font-mono);
  background: rgba(0,0,0,0.6); color: #fff;
  padding: 2px 7px; border-radius: 4px;
  backdrop-filter: blur(6px);
}

.result-info { padding: 18px 20px; display: flex; flex-direction: column; gap: 12px; }

.result-top {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
}
.result-title {
  font-family: var(--font-display); font-size: 16px; font-weight: 700; line-height: 1.3;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.result-author {
  display: flex; align-items: center; gap: 5px;
  font-size: 12.5px; color: var(--text-md); margin-top: 4px;
}
.result-stats {
  display: flex; flex-direction: column; gap: 4px; flex-shrink: 0;
}
.stat-pill {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: var(--text-md); white-space: nowrap;
}

.nowm-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px;
  background: rgba(27,255,164,0.08); border: 1px solid rgba(27,255,164,0.2);
  border-radius: var(--r-sm); font-size: 12.5px; font-weight: 600; color: var(--mint);
  width: fit-content;
}

/* Actions */
.actions { display: flex; flex-direction: column; gap: 8px; }
.action-primary {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 12px; background: var(--mint); color: #000;
  border: none; border-radius: var(--r-md);
  font-family: var(--font-body); font-size: 14.5px; font-weight: 700;
  cursor: pointer; text-decoration: none;
  transition: opacity 0.15s, transform 0.15s;
}
.action-primary:hover { opacity: 0.88; transform: translateY(-1px); }
.action-primary--sm { padding: 8px 14px; font-size: 13px; border-radius: var(--r-sm); }

.action-row { display: flex; gap: 8px; flex-wrap: wrap; }
.action-sec {
  flex: 1; min-width: 130px;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px 12px;
  background: transparent; border: 1px solid var(--border-md);
  border-radius: var(--r-md); color: var(--text-hi);
  font-size: 13px; font-weight: 500; text-decoration: none; cursor: pointer;
  transition: all 0.15s;
}
.action-sec:hover { background: var(--bg-2); border-color: var(--border-hi); }

/* Formats */
.formats-wrap { border-top: 1px solid var(--border); padding-top: 10px; }
.formats-toggle {
  display: flex; align-items: center; gap: 6px;
  background: none; border: none; color: var(--text-md); font-size: 12.5px;
  font-family: var(--font-body); cursor: pointer; padding: 0;
  transition: color 0.15s;
}
.formats-toggle:hover { color: var(--text-hi); }
.formats-toggle .flip { transform: rotate(180deg); }
.formats-toggle svg:last-child { transition: transform 0.2s; }

.formats-list {
  margin-top: 8px;
  border: 1px solid var(--border); border-radius: var(--r-md); overflow: hidden;
}
.fmt-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  text-decoration: none; color: var(--text-hi); font-size: 13px;
  border-bottom: 1px solid var(--border); transition: background 0.12s;
}
.fmt-item:last-child { border: none; }
.fmt-item:hover { background: var(--bg-2); }
.fmt-q   { font-weight: 700; width: 44px; }
.fmt-ext { font-family: var(--font-mono); font-size: 11px; color: var(--text-md); }
.fmt-sz  { font-size: 11px; color: var(--text-md); margin-left: auto; }
.fmt-wm  { font-size: 9px; font-weight: 700; background: var(--mint); color: #000; padding: 1px 5px; border-radius: 3px; }
.fmt-dl  { color: var(--text-lo); }

.drop-enter-active { transition: all 0.2s var(--ease); }
.drop-leave-active { transition: all 0.14s var(--ease); }
.drop-enter-from   { opacity: 0; transform: translateY(-4px); }
.drop-leave-to     { opacity: 0; }

/* ── Playlist card ────────────────────────────────────────────────────────── */
.playlist-card {
  margin-top: 14px;
  background: var(--bg-1); border: 1px solid var(--border); border-radius: var(--r-xl); overflow: hidden;
}
.playlist-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 16px 20px; background: var(--bg-2); border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.playlist-head__info { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.playlist-icon { color: var(--mint); flex-shrink: 0; }
.playlist-title { font-family: var(--font-display); font-size: 15px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.playlist-sub   { font-size: 12px; color: var(--text-md); margin-top: 2px; }

.playlist-items { max-height: 480px; overflow-y: auto; }
.pl-row {
  display: flex; align-items: center; gap: 12px;
  padding: 11px 20px; border-bottom: 1px solid var(--border);
  transition: background 0.12s;
}
.pl-row:last-child { border: none; }
.pl-row:hover { background: var(--bg-2); }
.pl-row--err { opacity: 0.45; }

.pl-num {
  font-family: var(--font-mono); font-size: 11px; color: var(--text-lo);
  min-width: 20px; text-align: right; flex-shrink: 0;
}
.pl-info  { flex: 1; min-width: 0; }
.pl-title { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pl-meta  { font-size: 11px; color: var(--text-md); margin-top: 2px; }
.pl-dl {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: var(--r-sm);
  background: var(--bg); border: 1px solid var(--border);
  color: var(--text-md); text-decoration: none; flex-shrink: 0;
  transition: all 0.15s;
}
.pl-dl:hover { background: var(--mint-dim); border-color: rgba(27,255,164,0.3); color: var(--mint); }
.pl-err { color: var(--danger); flex-shrink: 0; }

/* Error bar */
.error-bar {
  display: flex; align-items: center; gap: 10px;
  margin-top: 14px; padding: 12px 16px;
  background: rgba(244,63,94,0.06); border: 1px solid rgba(244,63,94,0.2);
  border-radius: var(--r-lg); color: var(--danger); font-size: 13.5px;
}
.error-bar span { flex: 1; }
.error-bar button {
  background: none; border: none; color: var(--text-lo);
  cursor: pointer; padding: 2px; border-radius: 4px; display: flex;
  transition: all 0.15s;
}
.error-bar button:hover { color: var(--text-hi); background: var(--bg-2); }

/* ── Info section ─────────────────────────────────────────────────────────── */
.info-section {
  padding: 48px 0 72px;
  border-top: 1px solid var(--border);
}
.info-grid {
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px;
}
.info-card {
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--r-lg); padding: 20px 18px;
  transition: all 0.2s;
}
.info-card:hover { border-color: var(--border-md); transform: translateY(-2px); }
.info-icon {
  width: 38px; height: 38px; background: var(--mint-dim); border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center;
  color: var(--mint); margin-bottom: 14px;
}
.info-title { font-family: var(--font-display); font-size: 14px; font-weight: 700; margin-bottom: 6px; }
.info-desc  { font-size: 12.5px; color: var(--text-md); line-height: 1.55; }

/* Transitions */
.fade-up-enter-active { transition: all 0.3s cubic-bezier(0.34,1.4,0.64,1); }
.fade-up-leave-active { transition: all 0.18s; }
.fade-up-enter-from   { opacity: 0; transform: translateY(12px) scale(0.98); }
.fade-up-leave-to     { opacity: 0; }

/* ── Responsive ────────────────────────────────────────────────────────────── */
/* Medium — colonne gauche plus étroite */
@media (max-width: 960px) {
  .extractor-grid { grid-template-columns: 360px 1fr; }
}
/* Tablette/mobile — une seule colonne */
@media (max-width: 720px) {
  .extractor-grid { grid-template-columns: 1fr; }
  .empty-hint { display: none; }
  .info-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 560px) {
  .options-row { flex-wrap: wrap; }
  .go-btn      { width: 100%; justify-content: center; }
  .result-thumb { height: 160px; }
  .action-row  { flex-direction: column; }
  .action-sec  { flex: unset; width: 100%; }
  .playlist-head { gap: 8px; }
}
@media (max-width: 380px) {
  .info-grid { grid-template-columns: 1fr; }
}
</style>
