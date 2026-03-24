<template>
  <div class="home">

    <!-- Hero -->
    <section class="hero">
      <div class="hero__bg">
        <div class="orb orb--1"></div>
        <div class="orb orb--2"></div>
        <div class="orb orb--3"></div>
      </div>

      <div class="hero__content">
        <div class="hero__badge">
          <span>PWA</span> · Partager → WaziScope → Télécharger
        </div>
        <h1 class="hero__title">
          Télécharge<br>
          <span class="gradient-text">n'importe quelle</span><br>
          vidéo
        </h1>
        <p class="hero__sub">
          TikTok sans watermark · Pinterest · Facebook<br>
          <em>Installe l'app, puis appuie sur "Partager" dans n'importe quelle app</em>
        </p>
      </div>
    </section>

    <!-- Input principal -->
    <section class="extractor-section">
      <div class="container">

        <!-- Platforms -->
        <div class="platforms">
          <div
            v-for="p in platforms"
            :key="p.id"
            :class="['platform-chip', `platform-chip--${p.id}`, { active: activePlatform === p.id }]"
          >
            <span>{{ p.icon }}</span>
            <span>{{ p.name }}</span>
            <span v-if="p.no_watermark" class="nowm-badge">No WM</span>
          </div>
        </div>

        <!-- URL Input -->
        <div class="input-card">
          <div class="input-wrap">
            <span class="input-icon">🔗</span>
            <input
              v-model="inputUrl"
              type="url"
              placeholder="Coller l'URL de la vidéo ici..."
              class="url-input"
              @keydown.enter="doExtract"
              :disabled="loading"
            />
            <button
              v-if="inputUrl"
              @click="inputUrl = ''"
              class="input-clear"
              aria-label="Effacer"
            >✕</button>
          </div>

          <button
            @click="doExtract"
            class="btn btn--primary btn--lg"
            :disabled="!inputUrl || loading"
          >
            <span v-if="loading" class="spinner"></span>
            <span v-else>⬇</span>
            {{ loading ? 'Analyse...' : 'Extraire la vidéo' }}
          </button>
        </div>

        <!-- Résultat -->
        <transition name="result">
          <div v-if="result" class="result-card">
            <!-- Thumbnail -->
            <div class="result-thumb">
              <img
                v-if="result.thumbnail"
                :src="result.thumbnail"
                :alt="result.title"
                class="thumb-img"
              />
              <div v-else class="thumb-placeholder">
                {{ getPlatformIcon(result.platform) }}
              </div>

              <!-- Platform tag -->
              <span :class="['platform-tag', `platform-tag--${result.platform}`]">
                {{ getPlatformIcon(result.platform) }} {{ result.platform }}
              </span>
            </div>

            <!-- Infos -->
            <div class="result-info">
              <h3 class="result-title">{{ result.title }}</h3>
              <div class="result-meta" v-if="result.duration">
                <span>⏱ {{ formatDuration(result.duration) }}</span>
                <span v-if="result.no_watermark_url" class="nowm-tag">✓ Sans watermark</span>
              </div>

              <!-- Actions -->
              <div class="result-actions">
                <!-- Téléchargement principal -->
                <a
                  :href="downloadUrl(result.no_watermark_url || result.best_url, result.title)"
                  :download="sanitizeFilename(result.title)"
                  class="btn btn--primary"
                  @click="onDownloadClick(result)"
                >
                  ⬇ Télécharger{{ result.platform === 'tiktok' ? ' (sans watermark)' : '' }}
                </a>

                <!-- Formats alternatifs -->
                <div v-if="result.formats && result.formats.length > 1" class="formats-dropdown">
                  <button @click="showFormats = !showFormats" class="btn btn--ghost btn--sm">
                    {{ showFormats ? '▲' : '▼' }} {{ result.formats.length }} formats
                  </button>
                  <transition name="dropdown">
                    <div v-if="showFormats" class="formats-list">
                      <a
                        v-for="fmt in result.formats.slice().reverse()"
                        :key="fmt.format_id"
                        :href="downloadUrl(fmt.url, result.title)"
                        :download="`${sanitizeFilename(result.title)}_${fmt.quality || fmt.format_id}.${fmt.ext}`"
                        class="format-item"
                        @click="showFormats = false"
                      >
                        <span class="fmt-quality">{{ fmt.quality || fmt.format_id }}</span>
                        <span class="fmt-ext">{{ fmt.ext }}</span>
                        <span v-if="fmt.filesize" class="fmt-size">{{ formatSize(fmt.filesize) }}</span>
                      </a>
                    </div>
                  </transition>
                </div>
              </div>
            </div>
          </div>
        </transition>

        <!-- Erreur -->
        <transition name="result">
          <div v-if="error" class="error-card">
            <span class="error-icon">⚠️</span>
            <div>
              <strong>Extraction impossible</strong>
              <p>{{ error }}</p>
            </div>
            <button @click="error = null" class="btn btn--ghost btn--sm">✕</button>
          </div>
        </transition>

      </div>
    </section>

    <!-- Comment ça marche -->
    <section class="howto">
      <div class="container">
        <h2 class="section-title">Comment télécharger depuis les apps ?</h2>
        <div class="steps">
          <div class="step" v-for="(step, i) in steps" :key="i">
            <div class="step__num">{{ i + 1 }}</div>
            <div class="step__icon">{{ step.icon }}</div>
            <h4 class="step__title">{{ step.title }}</h4>
            <p class="step__desc">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </section>

  </div>
</template>

<script setup>
import { ref, inject, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const notify = inject('notify')

// ─── State ────────────────────────────────────────────────────────────────────
const inputUrl   = ref('')
const loading    = ref(false)
const result     = ref(null)
const error      = ref(null)
const showFormats = ref(false)
const activePlatform = ref(null)

const platforms = ref([
  { id: 'tiktok',    name: 'TikTok',    icon: '🎵', no_watermark: true  },
  { id: 'pinterest', name: 'Pinterest', icon: '📌', no_watermark: false },
  { id: 'facebook',  name: 'Facebook',  icon: '📘', no_watermark: false },
])

const steps = [
  { icon: '📲', title: 'Installe WaziScope',    desc: 'Clique sur "Installer" ou ajoute à l\'écran d\'accueil depuis ton navigateur.' },
  { icon: '🎵', title: 'Ouvre TikTok/Pinterest', desc: 'Trouve la vidéo que tu veux télécharger dans l\'app.' },
  { icon: '↗️', title: 'Appuie sur Partager',   desc: 'Tape le bouton "Partager" de l\'app — WaziScope apparaît dans la liste.' },
  { icon: '⬇', title: 'Téléchargement auto',   desc: 'WaziScope reçoit le lien et lance le téléchargement immédiatement.' },
]

// ─── Auto-remplissage depuis Share Target ─────────────────────────────────────
onMounted(() => {
  const sharedUrl = route.query.url || route.query.shared
  if (sharedUrl) {
    inputUrl.value = decodeURIComponent(sharedUrl)
    doExtract()
  }

  // Écouter les partages entrants en temps réel
  window.addEventListener('waziscope:share', (e) => {
    inputUrl.value = e.detail.url
    doExtract()
  })
})

// ─── Extraction ───────────────────────────────────────────────────────────────
const doExtract = async () => {
  if (!inputUrl.value.trim()) return

  loading.value  = true
  result.value   = null
  error.value    = null
  showFormats.value = false

  // Détection plateforme active
  const url = inputUrl.value.toLowerCase()
  if (url.includes('tiktok'))    activePlatform.value = 'tiktok'
  else if (url.includes('pin'))  activePlatform.value = 'pinterest'
  else if (url.includes('face')) activePlatform.value = 'facebook'

  try {
    const response = await axios.post('/api/v1/extract', { url: inputUrl.value })
    const data = response.data

    if (!data.success) {
      error.value = data.message || 'Extraction échouée'
      return
    }

    result.value = data.data
    notify({ message: 'Vidéo trouvée !', type: 'success', icon: '✅' })

  } catch (e) {
    const msg = e.response?.data?.message || 'Erreur de connexion au serveur'
    error.value = msg
    notify({ message: msg, type: 'danger', icon: '❌' })
  } finally {
    loading.value = false
  }
}

// ─── Téléchargement ───────────────────────────────────────────────────────────
const downloadUrl = (url, title) => {
  if (!url) return '#'
  // Utiliser le proxy Laravel pour éviter les problèmes CORS
  return `/api/v1/download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(sanitizeFilename(title) + '.mp4')}`
}

const onDownloadClick = (video) => {
  // Sauvegarder dans l'historique
  const history = JSON.parse(localStorage.getItem('waziscope_history') || '[]')
  history.unshift({
    id: Date.now(),
    title: video.title,
    thumbnail: video.thumbnail,
    platform: video.platform,
    url: video.best_url,
    date: new Date().toISOString(),
  })
  localStorage.setItem('waziscope_history', JSON.stringify(history.slice(0, 50)))
  notify({ message: 'Téléchargement lancé !', type: 'success', icon: '⬇' })
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const sanitizeFilename = (title) =>
  (title || 'video').replace(/[^a-zA-Z0-9_\-. ]/g, '_').substring(0, 80)

const formatDuration = (secs) => {
  if (!secs) return ''
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const formatSize = (bytes) => {
  if (!bytes) return ''
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

const getPlatformIcon = (platform) => ({
  tiktok: '🎵', pinterest: '📌', facebook: '📘', instagram: '📸'
})[platform] || '🎬'
</script>

<style scoped>
/* ─── Hero ──────────────────────────────────────────────────────────────────── */
.hero {
  position: relative;
  padding: 80px 24px 60px;
  text-align: center;
  overflow: hidden;
}

.hero__bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.25;
  animation: float 8s ease-in-out infinite;
}
.orb--1 {
  width: 350px; height: 350px;
  background: #ff0050;
  top: -100px; left: -80px;
  animation-delay: 0s;
}
.orb--2 {
  width: 280px; height: 280px;
  background: #7928ca;
  top: -50px; right: -60px;
  animation-delay: -3s;
}
.orb--3 {
  width: 200px; height: 200px;
  background: #1877f2;
  bottom: 0; left: 40%;
  animation-delay: -5s;
}

@keyframes float {
  0%, 100% { transform: translateY(0px) scale(1); }
  50%       { transform: translateY(-20px) scale(1.05); }
}

.hero__content { position: relative; z-index: 1; }

.hero__badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 24px;
  font-family: var(--font-mono);
}
.hero__badge span {
  background: var(--grad);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 700;
}

.hero__title {
  font-family: var(--font-display);
  font-size: clamp(48px, 10vw, 80px);
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -2px;
  margin-bottom: 20px;
}

.gradient-text {
  background: var(--grad);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero__sub {
  color: var(--text-muted);
  font-size: 16px;
  line-height: 1.7;
  max-width: 400px;
  margin: 0 auto;
}
.hero__sub em {
  font-style: normal;
  color: var(--text-dim);
  font-size: 13px;
  display: block;
  margin-top: 8px;
}

/* ─── Extractor ──────────────────────────────────────────────────────────────── */
.extractor-section { padding: 0 0 64px; }

.container {
  max-width: 600px;
  margin: 0 auto;
  padding: 0 20px;
}

.platforms {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.platform-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition);
}
.platform-chip--tiktok.active    { border-color: var(--tiktok);    background: rgba(255,0,80,0.1); }
.platform-chip--pinterest.active { border-color: var(--pinterest); background: rgba(230,0,35,0.1); }
.platform-chip--facebook.active  { border-color: var(--facebook);  background: rgba(24,119,242,0.1); }

.nowm-badge {
  font-size: 9px;
  background: var(--success);
  color: white;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

/* ─── Input Card ──────────────────────────────────────────────────────────────── */
.input-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: border-color var(--transition);
}
.input-card:focus-within { border-color: var(--border-hover); }

.input-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  transition: border-color var(--transition);
}
.input-wrap:focus-within { border-color: rgba(255,0,80,0.4); }

.input-icon { font-size: 18px; flex-shrink: 0; }

.url-input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 13px;
  min-width: 0;
}
.url-input::placeholder { color: var(--text-dim); }

.input-clear {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all var(--transition);
}
.input-clear:hover { background: var(--bg-hover); color: var(--text); }

/* ─── Result Card ─────────────────────────────────────────────────────────────── */
.result-card {
  margin-top: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.result-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 16/9;
  background: var(--bg-hover);
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
}

.platform-tag {
  position: absolute;
  top: 12px; left: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  backdrop-filter: blur(8px);
}
.platform-tag--tiktok    { background: rgba(255,0,80,0.85); color: white; }
.platform-tag--pinterest { background: rgba(230,0,35,0.85); color: white; }
.platform-tag--facebook  { background: rgba(24,119,242,0.85); color: white; }

.result-info { padding: 20px; }

.result-title {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.nowm-tag {
  color: var(--success);
  font-weight: 600;
}

.result-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

/* Formats dropdown */
.formats-dropdown { position: relative; }
.formats-list {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-hover);
  border-radius: var(--radius);
  overflow: hidden;
  min-width: 220px;
  z-index: 10;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.format-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  text-decoration: none;
  color: var(--text);
  font-size: 13px;
  transition: background var(--transition);
  border-bottom: 1px solid var(--border);
}
.format-item:last-child { border: none; }
.format-item:hover { background: var(--bg-hover); }
.fmt-quality { font-weight: 600; flex: 1; }
.fmt-ext     { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
.fmt-size    { font-size: 11px; color: var(--text-muted); }

.dropdown-enter-active { transition: all 0.2s ease; }
.dropdown-leave-active { transition: all 0.15s ease; }
.dropdown-enter-from   { opacity: 0; transform: translateY(4px); }
.dropdown-leave-to     { opacity: 0; transform: translateY(4px); }

/* ─── Error Card ──────────────────────────────────────────────────────────────── */
.error-card {
  margin-top: 20px;
  background: rgba(239,68,68,0.07);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: var(--radius);
  padding: 16px 20px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.error-icon { font-size: 20px; flex-shrink: 0; margin-top: 2px; }
.error-card strong { display: block; font-size: 14px; margin-bottom: 4px; }
.error-card p { font-size: 13px; color: var(--text-muted); }
.error-card .btn { margin-left: auto; flex-shrink: 0; }

/* ─── Spinner ─────────────────────────────────────────────────────────────────── */
.spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── How to ──────────────────────────────────────────────────────────────────── */
.howto {
  padding: 48px 0;
  border-top: 1px solid var(--border);
}

.section-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  text-align: center;
  margin-bottom: 36px;
}

.steps {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (max-width: 480px) {
  .steps { grid-template-columns: 1fr 1fr; }
}

.step {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  text-align: center;
  transition: all var(--transition);
}
.step:hover {
  border-color: var(--border-hover);
  transform: translateY(-2px);
}

.step__num {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.step__icon { font-size: 28px; margin-bottom: 10px; }
.step__title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 6px;
}
.step__desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

/* ─── Result animation ────────────────────────────────────────────────────────── */
.result-enter-active { transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1); }
.result-leave-active { transition: all 0.2s ease; }
.result-enter-from   { opacity: 0; transform: scale(0.95) translateY(8px); }
.result-leave-to     { opacity: 0; transform: scale(0.95); }
</style>
