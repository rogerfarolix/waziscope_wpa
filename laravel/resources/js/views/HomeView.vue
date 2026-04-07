<template>
  <div class="home">

    <!-- ── Hero ─────────────────────────────────────────────────────────── -->
    <section class="hero">
      <div class="hero__noise" aria-hidden="true"></div>
      <div class="glow glow--a" aria-hidden="true"></div>
      <div class="glow glow--b" aria-hidden="true"></div>

      <div class="hero__body container">
        <!-- Platforms pill -->
        <div class="hero__pill">
          <Zap :size="11" />
          <span>TikTok · YouTube · Pinterest · Facebook · Instagram · LinkedIn · Twitter</span>
        </div>

        <h1 class="hero__h1">
          Télécharge<br>
          <span class="hero__accent">n'importe quelle</span><br>
          vidéo
        </h1>

        <p class="hero__sub">
          Installe l'app, appuie sur <strong>"Partager"</strong> dans TikTok
          ou YouTube — WaziScope reçoit le lien et télécharge automatiquement.
        </p>

        <!-- Feature badges -->
        <div class="hero__features">
          <span class="feat-badge">
            <ShieldCheck :size="12" />
            TikTok sans watermark
          </span>
          <span class="feat-badge">
            <ShieldOff :size="12" />
            Suppression de métadonnées
          </span>
          <span class="feat-badge">
            <Music :size="12" />
            Audio seul
          </span>
          <span class="feat-badge">
            <Layers :size="12" />
            Multi-qualité
          </span>
        </div>
      </div>
    </section>

    <!-- ── Extractor ────────────────────────────────────────────────────── -->
    <section class="extractor">
      <div class="container">

        <!-- Platform chips -->
        <div class="platforms" role="list">
          <div
            v-for="p in platforms"
            :key="p.id"
            :class="['platform', `platform--${p.id}`, { 'platform--active': detectedPlatform === p.id }]"
            role="listitem"
          >
            <component :is="platformIcon(p.id)" :size="13" />
            <span>{{ p.name }}</span>
            <span v-if="p.no_watermark" class="wm-chip">No WM</span>
          </div>
        </div>

        <!-- Input card -->
        <div class="card input-card">
          <div class="input-row">
            <div :class="['url-wrap', { 'url-wrap--focus': inputFocused }]">
              <Link2 :size="16" class="url-icon" />
              <input
                v-model="inputUrl"
                ref="inputEl"
                type="url"
                placeholder="Colle l'URL de la vidéo ici…"
                class="url-inp"
                autocomplete="off"
                autocorrect="off"
                spellcheck="false"
                @focus="inputFocused = true"
                @blur="inputFocused = false"
                @keydown.enter="doExtract"
                :disabled="loading"
              />
              <button v-if="inputUrl" class="url-clear" @click="clearInput" aria-label="Effacer">
                <X :size="13" />
              </button>
            </div>

            <button
              class="wz-btn wz-btn--mint extract-btn"
              :disabled="!inputUrl.trim() || loading"
              @click="doExtract"
            >
              <Loader2 v-if="loading" :size="16" class="spin" />
              <DownloadCloud v-else :size="16" />
              <span>{{ loading ? 'Analyse…' : 'Extraire' }}</span>
            </button>
          </div>

          <div class="input-hints">
            <button class="hint-btn" @click="pasteFromClipboard">
              <Clipboard :size="12" />
              <span>Coller depuis le presse-papiers</span>
            </button>
            <span class="hint-sep">·</span>
            <span class="hint-txt">Entrée pour lancer</span>
          </div>
        </div>

        <!-- Loading skeleton -->
        <div v-if="loading" class="card result-card result-card--skeleton">
          <div class="sk sk--thumb"></div>
          <div class="sk-body">
            <div class="sk sk--line sk--w70"></div>
            <div class="sk sk--line sk--w45"></div>
            <div class="sk sk--btn"></div>
          </div>
        </div>

        <!-- Result card -->
        <transition name="result">
          <div v-if="result && !loading" class="card result-card">

            <!-- Thumbnail -->
            <div class="thumb-wrap">
              <img
                v-if="result.thumbnail"
                :src="result.thumbnail"
                :alt="result.title"
                class="thumb-img"
                loading="lazy"
              />
              <div v-else class="thumb-fallback">
                <component :is="platformIcon(result.platform)" :size="36" />
              </div>

              <span v-if="result.duration" class="duration-badge">
                <Clock :size="10" />
                {{ fmtDuration(result.duration) }}
              </span>

              <span :class="['plat-badge', `plat-badge--${result.platform}`]">
                <component :is="platformIcon(result.platform)" :size="11" />
                {{ result.platform }}
              </span>
            </div>

            <!-- Body -->
            <div class="result-body">
              <div class="result-meta">
                <h3 class="result-title">{{ result.title }}</h3>
                <p v-if="result.author" class="result-author">
                  <UserRound :size="12" />
                  {{ result.author }}
                </p>
              </div>

              <div v-if="result.view_count || result.like_count" class="result-stats">
                <span v-if="result.view_count" class="stat">
                  <Eye :size="12" />
                  {{ fmtCount(result.view_count) }} vues
                </span>
                <span v-if="result.like_count" class="stat">
                  <Heart :size="12" />
                  {{ fmtCount(result.like_count) }}
                </span>
              </div>

              <div v-if="result.platform === 'tiktok' && result.no_watermark_url" class="nowm-callout">
                <ShieldCheck :size="13" />
                <span>Sans watermark disponible</span>
              </div>

              <!-- ── Download actions ───────────────────────────────────── -->
              <div class="dl-actions">

                <!-- Primary download -->
                <a
                  :href="result.proxy_download_url || dlProxyUrl(result.no_watermark_url || result.best_url, result.title)"
                  :download="safeFilename(result.title) + '.mp4'"
                  class="wz-btn wz-btn--mint wz-btn--blk"
                  @click="onDlClick(result)"
                >
                  <DownloadCloud :size="16" />
                  <span>Télécharger{{ result.platform === 'tiktok' ? ' (sans watermark)' : '' }}</span>
                </a>

                <!-- Secondary row: strip + audio -->
                <div class="dl-secondary">

                  <!-- Strip metadata -->
                  <a
                    v-if="ffmpegAvailable && (result.proxy_strip_url || stripUrl(result))"
                    :href="result.proxy_strip_url || stripUrl(result)"
                    :download="safeFilename(result.title) + '_clean.mp4'"
                    class="wz-btn wz-btn--outline dl-secondary__btn"
                    title="Télécharger sans aucune métadonnée (titre, auteur, GPS, dates…)"
                    @click="onDlClick(result)"
                  >
                    <ShieldOff :size="14" />
                    <span>Sans métadonnées</span>
                  </a>

                  <!-- ffmpeg indispo -->
                  <span
                    v-else-if="!ffmpegAvailable"
                    class="wz-btn wz-btn--ghost dl-secondary__btn dl-secondary__btn--disabled"
                    title="ffmpeg non disponible sur ce serveur"
                  >
                    <ShieldOff :size="14" />
                    <span>Sans métadonnées</span>
                  </span>

                  <!-- Audio only -->
                  <a
                    v-if="result.audio_only_url"
                    :href="dlProxyUrl(result.audio_only_url, result.title + '_audio')"
                    :download="safeFilename(result.title) + '.mp3'"
                    class="wz-btn wz-btn--outline dl-secondary__btn"
                  >
                    <Music :size="14" />
                    <span>Audio</span>
                  </a>
                </div>
              </div>

              <!-- Strip metadata info callout -->
              <div v-if="ffmpegAvailable" class="strip-info">
                <ShieldOff :size="11" />
                <span>
                  "Sans métadonnées" supprime le titre, l'auteur, les dates, le GPS
                  et toute info personnelle sans re-encoder la vidéo.
                </span>
              </div>

              <!-- Formats -->
              <div v-if="result.formats && result.formats.length > 1" class="formats-section">
                <button class="formats-toggle" @click="showFormats = !showFormats">
                  <Layers :size="13" />
                  <span>{{ result.formats.length }} formats disponibles</span>
                  <ChevronDown :size="13" :class="{ 'rotate-180': showFormats }" class="fmt-chevron" />
                </button>

                <transition name="fmt-drop">
                  <div v-if="showFormats" class="formats-grid">
                    <a
                      v-for="fmt in [...result.formats].reverse()"
                      :key="fmt.format_id"
                      :href="fmt.proxy_url || dlProxyUrl(fmt.url, result.title)"
                      :download="`${safeFilename(result.title)}_${fmt.quality || fmt.format_id}.${fmt.ext}`"
                      class="fmt-row"
                    >
                      <span class="fmt-q">{{ fmt.height ? fmt.height + 'p' : fmt.quality }}</span>
                      <span class="fmt-ext">{{ fmt.ext }}</span>
                      <span v-if="fmt.filesize" class="fmt-sz">{{ fmtSize(fmt.filesize) }}</span>
                      <span v-if="fmt.no_watermark" class="fmt-nowm">No WM</span>
                      <!-- Strip icon per format -->
                      <a
                        v-if="ffmpegAvailable && fmt.strip_url"
                        :href="fmt.strip_url"
                        :download="`${safeFilename(result.title)}_${fmt.quality || fmt.format_id}_clean.mp4`"
                        class="fmt-strip"
                        title="Télécharger sans métadonnées"
                        @click.stop
                      >
                        <ShieldOff :size="11" />
                      </a>
                      <Download :size="12" class="fmt-dl" />
                    </a>
                  </div>
                </transition>
              </div>
            </div>
          </div>
        </transition>

        <!-- Error -->
        <transition name="result">
          <div v-if="errorMsg" class="error-card">
            <AlertCircle :size="17" />
            <div class="error-body">
              <strong>Extraction impossible</strong>
              <p>{{ errorMsg }}</p>
            </div>
            <button class="wz-btn wz-btn--ghost wz-btn--sm" @click="errorMsg = null">
              <X :size="13" />
            </button>
          </div>
        </transition>

      </div>
    </section>

    <!-- ── How it works ─────────────────────────────────────────────────── -->
    <section class="howto">
      <div class="container">
        <div class="howto__header">
          <h2 class="howto__title">Comment ça marche ?</h2>
          <p class="howto__sub">Télécharge directement depuis les apps en 4 étapes</p>
        </div>

        <ol class="steps">
          <li v-for="(step, i) in steps" :key="i" class="step">
            <div class="step__num">0{{ i + 1 }}</div>
            <div class="step__icon-wrap">
              <component :is="step.icon" :size="22" />
            </div>
            <h4 class="step__title">{{ step.title }}</h4>
            <p class="step__desc">{{ step.desc }}</p>
          </li>
        </ol>

        <!-- Features grid -->
        <div class="features-grid">
          <div v-for="f in features" :key="f.title" class="feat-card">
            <div class="feat-card__icon">
              <component :is="f.icon" :size="20" />
            </div>
            <h4 class="feat-card__title">{{ f.title }}</h4>
            <p class="feat-card__desc">{{ f.desc }}</p>
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
  Zap, Clipboard, Smartphone, Share2, AppWindow, Music2,
  Youtube, Pin, Facebook, Instagram, Linkedin, Twitter, Film,
} from 'lucide-vue-next'

const route  = useRoute()
const notify = inject('notify')

// ─── State ───────────────────────────────────────────────────────────────────
const inputUrl         = ref('')
const inputEl          = ref(null)
const inputFocused     = ref(false)
const loading          = ref(false)
const result           = ref(null)
const errorMsg         = ref(null)
const showFormats      = ref(false)
const detectedPlatform = ref(null)
const ffmpegAvailable  = ref(false)   // true si ffmpeg est dispo côté serveur

// ─── Platforms ───────────────────────────────────────────────────────────────
const platforms = ref([
  { id: 'tiktok',    name: 'TikTok',    no_watermark: true  },
  { id: 'youtube',   name: 'YouTube',   no_watermark: false },
  { id: 'pinterest', name: 'Pinterest', no_watermark: false },
  { id: 'facebook',  name: 'Facebook',  no_watermark: false },
  { id: 'instagram', name: 'Instagram', no_watermark: false },
  { id: 'linkedin',  name: 'LinkedIn',  no_watermark: false },
  { id: 'twitter',   name: 'Twitter/X', no_watermark: false },
])

const platformIcon = (id) => ({
  tiktok: Music2, youtube: Youtube, pinterest: Pin,
  facebook: Facebook, instagram: Instagram, linkedin: Linkedin, twitter: Twitter,
}[id] || Film)

// ─── Steps ───────────────────────────────────────────────────────────────────
const steps = [
  { icon: Smartphone,   title: 'Installe WaziScope',     desc: 'Ajoute l\'app à ton écran d\'accueil depuis le navigateur.' },
  { icon: AppWindow,    title: 'Ouvre TikTok / YouTube',  desc: 'Trouve la vidéo que tu veux télécharger.' },
  { icon: Share2,       title: 'Appuie sur Partager',     desc: 'WaziScope apparaît dans la liste des apps.' },
  { icon: DownloadCloud, title: 'Téléchargement auto',    desc: 'Le lien arrive, l\'extraction démarre automatiquement.' },
]

// ─── Feature cards ────────────────────────────────────────────────────────────
const features = [
  {
    icon: ShieldCheck,
    title: 'Sans watermark',
    desc: 'Télécharge les vidéos TikTok sans le logo watermark via l\'API mobile officielle.',
  },
  {
    icon: ShieldOff,
    title: 'Suppression de métadonnées',
    desc: 'Efface automatiquement toutes les métadonnées embarquées : titre, auteur, GPS, dates, infos de l\'appareil — sans re-encoder la vidéo.',
  },
  {
    icon: Music,
    title: 'Audio seul',
    desc: 'Extrait uniquement la piste audio en MP3 depuis YouTube, TikTok et les autres plateformes.',
  },
  {
    icon: Layers,
    title: 'Multi-qualité',
    desc: 'Choisis parmi toutes les résolutions disponibles : 1080p, 720p, 480p ou la meilleure qualité automatique.',
  },
]

// ─── Mount ───────────────────────────────────────────────────────────────────
onMounted(async () => {
  const sharedUrl = route.query.url || route.query.shared
  if (sharedUrl) {
    inputUrl.value = decodeURIComponent(String(sharedUrl))
    doExtract()
    return
  }

  if (route.query.action === 'paste') {
    await pasteFromClipboard()
  }

  window.addEventListener('wzs:share', (e) => {
    inputUrl.value = e.detail.url
    doExtract()
  })

  // Charger les plateformes + vérifier ffmpeg
  try {
    const [platRes, capRes] = await Promise.all([
      axios.get('/api/v1/platforms').catch(() => null),
      axios.get('/api/v1/capabilities').catch(() => null),
    ])
    if (platRes?.data?.platforms) platforms.value = platRes.data.platforms
    if (capRes?.data?.ffmpeg !== undefined) ffmpegAvailable.value = capRes.data.ffmpeg
  } catch { /* garder fallback */ }
})

// ─── Clipboard ───────────────────────────────────────────────────────────────
const pasteFromClipboard = async () => {
  try {
    const text = await navigator.clipboard.readText()
    if (text?.startsWith('http')) {
      inputUrl.value = text.trim()
      detectPlatformFromUrl(inputUrl.value)
      notify({ message: 'URL collée !', type: 'success' })
    }
  } catch {
    notify({ message: 'Accès presse-papiers refusé', type: 'warning' })
  }
}

// ─── Platform detection ───────────────────────────────────────────────────────
const detectPlatformFromUrl = (url) => {
  const u = url.toLowerCase()
  if (u.includes('tiktok'))                             return (detectedPlatform.value = 'tiktok')
  if (u.includes('youtu'))                              return (detectedPlatform.value = 'youtube')
  if (u.includes('pin'))                                return (detectedPlatform.value = 'pinterest')
  if (u.includes('facebook') || u.includes('fb.'))     return (detectedPlatform.value = 'facebook')
  if (u.includes('instagram'))                          return (detectedPlatform.value = 'instagram')
  if (u.includes('linkedin'))                           return (detectedPlatform.value = 'linkedin')
  if (u.includes('twitter') || u.includes('x.com'))    return (detectedPlatform.value = 'twitter')
  detectedPlatform.value = null
}

const clearInput = () => {
  inputUrl.value = ''
  detectedPlatform.value = null
  result.value   = null
  errorMsg.value = null
  inputEl.value?.focus()
}

// ─── Extract ─────────────────────────────────────────────────────────────────
const doExtract = async () => {
  const url = inputUrl.value.trim()
  if (!url) return

  detectPlatformFromUrl(url)
  loading.value     = true
  result.value      = null
  errorMsg.value    = null
  showFormats.value = false

  try {
    const res  = await axios.post('/api/v1/extract', { url })
    const data = res.data

    if (!data.success) {
      errorMsg.value = data.message || 'Extraction échouée'
      return
    }

    result.value = data.data

    // Mettre à jour la dispo ffmpeg depuis la réponse
    if (data.ffmpeg_available !== undefined) {
      ffmpegAvailable.value = data.ffmpeg_available
    }

    notify({ message: 'Vidéo trouvée !', type: 'success' })

  } catch (e) {
    errorMsg.value = e.response?.data?.message || 'Erreur de connexion au serveur'
    notify({ message: errorMsg.value, type: 'danger' })
  } finally {
    loading.value = false
  }
}

// ─── URL builders ─────────────────────────────────────────────────────────────
const dlProxyUrl = (url, title) => {
  if (!url) return '#'
  return `/api/v1/download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(safeFilename(title) + '.mp4')}`
}

const stripUrl = (video) => {
  const url = video?.no_watermark_url || video?.best_url
  if (!url) return '#'
  return `/api/v1/strip?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(safeFilename(video.title))}&platform=${video.platform}`
}

// ─── History ─────────────────────────────────────────────────────────────────
const onDlClick = (video) => {
  try {
    const history = JSON.parse(localStorage.getItem('wzs_history') || '[]')
    history.unshift({
      id: Date.now(),
      title: video.title,
      thumbnail: video.thumbnail,
      platform: video.platform,
      url: video.best_url,
      date: new Date().toISOString(),
    })
    localStorage.setItem('wzs_history', JSON.stringify(history.slice(0, 50)))
  } catch { /* localStorage indisponible */ }
  notify({ message: 'Téléchargement lancé !', type: 'success' })
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
const safeFilename = (s) =>
  (s || 'video').replace(/[^\w\-. ]/g, '_').substring(0, 80)

const fmtDuration = (s) => {
  if (!s) return ''
  const m = Math.floor(s / 60), sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

const fmtCount = (n) => {
  if (!n) return ''
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return String(n)
}

const fmtSize = (b) => {
  if (!b) return ''
  return b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`
}
</script>

<style scoped>
/* ── Hero ─────────────────────────────────────────────────────────────────── */
.hero {
  position: relative;
  padding: 72px 0 52px;
  overflow: hidden;
}
.hero__noise {
  position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  opacity: 0.025;
  pointer-events: none;
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  pointer-events: none;
}
.glow--a {
  width: 420px; height: 420px;
  background: radial-gradient(circle, rgba(27,255,164,0.18) 0%, transparent 70%);
  top: -120px; left: -80px;
  animation: glow-drift 9s ease-in-out infinite;
}
.glow--b {
  width: 300px; height: 300px;
  background: radial-gradient(circle, rgba(24,119,242,0.14) 0%, transparent 70%);
  top: -60px; right: -50px;
  animation: glow-drift 12s ease-in-out infinite reverse;
}
@keyframes glow-drift {
  0%, 100% { transform: translate(0, 0); }
  50%       { transform: translate(14px, -18px); }
}

.hero__body { position: relative; z-index: 1; text-align: center; }

.hero__pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  background: var(--mint-dim);
  border: 1px solid rgba(27,255,164,0.2);
  border-radius: 20px;
  font-size: 11.5px;
  font-family: var(--font-mono);
  color: var(--mint);
  margin-bottom: 22px;
}

.hero__h1 {
  font-family: var(--font-display);
  font-size: clamp(44px, 10vw, 76px);
  font-weight: 800;
  line-height: 1.04;
  letter-spacing: -1.5px;
  margin-bottom: 18px;
}
.hero__accent { color: var(--mint); }

.hero__sub {
  color: var(--text-md);
  font-size: 15.5px;
  max-width: 420px;
  margin: 0 auto 24px;
  line-height: 1.65;
}
.hero__sub strong { color: var(--text-hi); }

/* Feature badges */
.hero__features {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
.feat-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-md);
}
.feat-badge svg { color: var(--mint); }

/* ── Extractor ────────────────────────────────────────────────────────────── */
.extractor { padding: 0 0 72px; }

/* Platforms */
.platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  justify-content: center;
  margin-bottom: 20px;
}
.platform {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-md);
  transition: all 0.18s var(--ease);
}
.platform--active,
.platform:hover { color: var(--text-hi); border-color: var(--border-md); }

.platform--tiktok.platform--active    { border-color: var(--col-tiktok);    color: var(--col-tiktok); }
.platform--youtube.platform--active   { border-color: var(--col-youtube);   color: var(--col-youtube); }
.platform--pinterest.platform--active { border-color: var(--col-pinterest); color: var(--col-pinterest); }
.platform--facebook.platform--active  { border-color: var(--col-facebook);  color: var(--col-facebook); }
.platform--instagram.platform--active { border-color: var(--col-instagram); color: var(--col-instagram); }
.platform--linkedin.platform--active  { border-color: var(--col-linkedin);  color: var(--col-linkedin); }
.platform--twitter.platform--active   { border-color: var(--col-twitter);   color: var(--col-twitter); }

.wm-chip {
  font-size: 9px; font-weight: 700;
  background: var(--mint); color: #000;
  padding: 0px 5px; border-radius: 4px; letter-spacing: 0.4px;
}

/* Card */
.card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  overflow: hidden;
  transition: border-color 0.2s var(--ease);
}
.card:hover { border-color: var(--border-md); }

/* Input card */
.input-card { padding: 18px; }
.input-row { display: flex; gap: 10px; align-items: stretch; }

.url-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg);
  border: 1px solid var(--border-md);
  border-radius: var(--r-md);
  padding: 11px 14px;
  min-width: 0;
  transition: border-color 0.18s var(--ease), box-shadow 0.18s var(--ease);
}
.url-wrap--focus {
  border-color: var(--mint);
  box-shadow: 0 0 0 3px var(--mint-glow);
}
.url-icon { color: var(--text-lo); flex-shrink: 0; }
.url-inp {
  flex: 1;
  background: none; border: none; outline: none;
  color: var(--text-hi);
  font-family: var(--font-mono);
  font-size: 13px; min-width: 0;
}
.url-inp::placeholder { color: var(--text-lo); }
.url-clear {
  background: none; border: none;
  color: var(--text-lo); cursor: pointer;
  padding: 2px; border-radius: 4px;
  display: flex; transition: all 0.15s; flex-shrink: 0;
}
.url-clear:hover { background: var(--bg-2); color: var(--text-hi); }

.extract-btn { border-radius: var(--r-md); padding: 11px 22px; flex-shrink: 0; }

.input-hints {
  display: flex; align-items: center; gap: 8px;
  margin-top: 10px; padding: 0 2px;
}
.hint-btn {
  display: flex; align-items: center; gap: 5px;
  background: none; border: none;
  color: var(--text-lo); font-size: 12px; font-family: var(--font-body);
  cursor: pointer; padding: 0;
  transition: color 0.15s;
}
.hint-btn:hover { color: var(--mint); }
.hint-sep, .hint-txt { font-size: 12px; color: var(--text-lo); }

/* Skeleton */
.result-card--skeleton { margin-top: 14px; display: flex; }
.sk {
  background: linear-gradient(90deg, var(--bg-2) 25%, var(--bg-3) 50%, var(--bg-2) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--r-sm);
}
@keyframes shimmer { to { background-position: -200% 0; } }
.sk--thumb { width: 140px; min-height: 120px; border-radius: 0; flex-shrink: 0; }
.sk-body   { flex: 1; padding: 18px; display: flex; flex-direction: column; gap: 10px; }
.sk--line  { height: 14px; border-radius: 4px; }
.sk--w70   { width: 70%; }
.sk--w45   { width: 45%; }
.sk--btn   { height: 38px; border-radius: var(--r-md); margin-top: 4px; }

/* Result card */
.result-card { margin-top: 14px; display: flex; }

.thumb-wrap {
  position: relative;
  width: 140px; min-height: 120px;
  flex-shrink: 0;
  background: var(--bg-2);
}
.thumb-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb-fallback {
  width: 100%; height: 100%; min-height: 120px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-lo);
}

.duration-badge {
  position: absolute; bottom: 6px; right: 6px;
  display: flex; align-items: center; gap: 4px;
  background: rgba(0,0,0,0.72); color: #fff;
  font-size: 10px; font-family: var(--font-mono);
  padding: 2px 6px; border-radius: 4px;
  backdrop-filter: blur(4px);
}

.plat-badge {
  position: absolute; top: 6px; left: 6px;
  display: flex; align-items: center; gap: 4px;
  padding: 3px 8px; border-radius: 5px;
  font-size: 10px; font-weight: 700; text-transform: capitalize;
  backdrop-filter: blur(6px);
}
.plat-badge--tiktok    { background: rgba(255,45,85,0.85);   color: #fff; }
.plat-badge--youtube   { background: rgba(255,0,51,0.85);    color: #fff; }
.plat-badge--pinterest { background: rgba(230,0,35,0.85);    color: #fff; }
.plat-badge--facebook  { background: rgba(24,119,242,0.85);  color: #fff; }
.plat-badge--instagram { background: rgba(225,48,108,0.85);  color: #fff; }
.plat-badge--linkedin  { background: rgba(10,102,194,0.85);  color: #fff; }
.plat-badge--twitter   { background: rgba(29,161,242,0.85);  color: #fff; }

.result-body {
  flex: 1; min-width: 0;
  padding: 16px 18px;
  display: flex; flex-direction: column; gap: 10px;
}
.result-title {
  font-family: var(--font-display);
  font-size: 15px; font-weight: 700; line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.result-author {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; color: var(--text-md);
}

.result-stats { display: flex; align-items: center; gap: 12px; }
.stat { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-md); }

.nowm-callout {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  background: rgba(27,255,164,0.08);
  border: 1px solid rgba(27,255,164,0.2);
  border-radius: var(--r-sm);
  color: var(--mint); font-size: 12px; font-weight: 600;
}

/* Download actions */
.dl-actions { display: flex; flex-direction: column; gap: 7px; }

.dl-secondary {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}

.dl-secondary__btn {
  flex: 1;
  min-width: 120px;
}

.dl-secondary__btn--disabled {
  opacity: 0.35;
  cursor: not-allowed;
  pointer-events: none;
}

/* Strip info */
.strip-info {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  font-size: 11px;
  color: var(--text-lo);
  line-height: 1.5;
}
.strip-info svg { color: var(--text-lo); flex-shrink: 0; margin-top: 1px; }

/* Formats */
.formats-section { border-top: 1px solid var(--border); padding-top: 10px; }
.formats-toggle {
  display: flex; align-items: center; gap: 7px;
  background: none; border: none;
  color: var(--text-md); font-size: 12.5px; font-family: var(--font-body);
  cursor: pointer; padding: 0;
  transition: color 0.15s;
}
.formats-toggle:hover { color: var(--text-hi); }
.fmt-chevron { transition: transform 0.2s var(--ease); }
.rotate-180  { transform: rotate(180deg); }

.formats-grid {
  margin-top: 8px;
  display: flex; flex-direction: column; gap: 1px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  overflow: hidden;
}
.fmt-row {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 12px;
  text-decoration: none;
  color: var(--text-hi);
  font-size: 13px;
  transition: background 0.15s;
  border-bottom: 1px solid var(--border);
}
.fmt-row:last-child { border: none; }
.fmt-row:hover { background: var(--bg-2); }
.fmt-q   { font-weight: 600; width: 44px; }
.fmt-ext { font-family: var(--font-mono); font-size: 11px; color: var(--text-md); }
.fmt-sz  { font-size: 11px; color: var(--text-md); margin-left: auto; }
.fmt-nowm { font-size: 9px; font-weight: 700; background: var(--mint); color: #000; padding: 1px 5px; border-radius: 3px; }
.fmt-strip {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px;
  border-radius: 4px;
  background: rgba(255,255,255,0.05);
  color: var(--text-lo);
  text-decoration: none;
  transition: all 0.15s;
  flex-shrink: 0;
}
.fmt-strip:hover { background: rgba(255,255,255,0.1); color: var(--text-hi); }
.fmt-dl  { color: var(--text-lo); margin-left: 4px; }

.fmt-drop-enter-active { transition: all 0.22s var(--ease); }
.fmt-drop-leave-active { transition: all 0.15s var(--ease); }
.fmt-drop-enter-from   { opacity: 0; transform: translateY(-4px); }
.fmt-drop-leave-to     { opacity: 0; }

/* Error */
.error-card {
  margin-top: 14px;
  background: rgba(244,63,94,0.06);
  border: 1px solid rgba(244,63,94,0.22);
  border-radius: var(--r-lg);
  padding: 14px 18px;
  display: flex; align-items: flex-start; gap: 10px;
  color: var(--danger);
}
.error-body { flex: 1; }
.error-body strong { display: block; font-size: 13.5px; margin-bottom: 3px; color: var(--text-hi); }
.error-body p      { font-size: 13px; color: var(--text-md); }
.error-card .wz-btn { flex-shrink: 0; }

/* Result transitions */
.result-enter-active { transition: all 0.32s cubic-bezier(0.34, 1.4, 0.64, 1); }
.result-leave-active { transition: all 0.2s var(--ease); }
.result-enter-from   { opacity: 0; transform: translateY(10px) scale(0.98); }
.result-leave-to     { opacity: 0; }

/* ── How To + Features ────────────────────────────────────────────────────── */
.howto {
  padding: 56px 0 80px;
  border-top: 1px solid var(--border);
}
.howto__header { text-align: center; margin-bottom: 40px; }
.howto__title {
  font-family: var(--font-display);
  font-size: 26px; font-weight: 700; margin-bottom: 6px;
}
.howto__sub { color: var(--text-md); font-size: 14.5px; }

.steps {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}
.step {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 22px 20px;
  transition: all 0.22s var(--ease);
}
.step:hover {
  border-color: var(--border-md);
  transform: translateY(-2px);
  background: var(--bg-2);
}
.step__num { font-family: var(--font-mono); font-size: 10px; color: var(--mint); margin-bottom: 10px; opacity: 0.7; }
.step__icon-wrap {
  width: 42px; height: 42px;
  background: var(--bg-2);
  border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center;
  color: var(--mint); margin-bottom: 12px;
}
.step__title { font-family: var(--font-display); font-size: 14px; font-weight: 700; margin-bottom: 5px; }
.step__desc  { font-size: 12.5px; color: var(--text-md); line-height: 1.55; }

/* Feature cards */
.features-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.feat-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 18px;
  transition: all 0.22s var(--ease);
}
.feat-card:hover {
  border-color: var(--border-md);
  transform: translateY(-2px);
}
.feat-card__icon {
  width: 38px; height: 38px;
  background: var(--mint-dim);
  border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center;
  color: var(--mint); margin-bottom: 12px;
}
.feat-card__title { font-family: var(--font-display); font-size: 13.5px; font-weight: 700; margin-bottom: 5px; }
.feat-card__desc  { font-size: 12px; color: var(--text-md); line-height: 1.55; }

/* ── Responsive ────────────────────────────────────────────────────────────── */
@media (max-width: 520px) {
  .input-row    { flex-direction: column; }
  .extract-btn  { width: 100%; }
  .result-card  { flex-direction: column; }
  .thumb-wrap   { width: 100%; min-height: 180px; }
  .steps        { grid-template-columns: 1fr 1fr; }
  .features-grid { grid-template-columns: 1fr 1fr; }
  .dl-secondary { flex-direction: column; }
  .dl-secondary__btn { flex: unset; width: 100%; }
}
</style>
