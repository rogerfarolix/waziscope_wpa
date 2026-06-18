<template>
  <div class="home">

    <!-- ══ HERO ══════════════════════════════════════════════════════════════ -->
    <section class="hero">
      <div class="hero__glow" aria-hidden="true"></div>

      <div class="hero__content">
        <p class="hero__eyebrow">
          <span class="dot-pulse"></span>Téléchargement instantané
        </p>

        <h1 class="hero__title">
          Toute vidéo,<br><span class="hero__accent">sans limite.</span>
        </h1>

        <p class="hero__desc">
          TikTok sans watermark · YouTube 4K · Playlists · Longs métrages · Audio MP3
        </p>

        <!-- ── Barre principale ── -->
        <div class="search-block">
          <div class="mode-pill">
            <button :class="['mpill', { 'mpill--on': mode === 'single' }]"   @click="mode = 'single'">
              <Film :size="12" />Vidéo
            </button>
            <button :class="['mpill', { 'mpill--on': mode === 'playlist' }]" @click="mode = 'playlist'">
              <List :size="12" />Playlist
            </button>
          </div>

          <div :class="['search-input', { 'search-input--focus': focused }]">
            <Link2 :size="16" class="si-icon" />
            <input
              v-model="inputUrl"
              ref="inputEl"
              type="url"
              :placeholder="mode === 'playlist' ? 'URL playlist YouTube, Vimeo…' : 'Colle le lien ici…'"
              autocomplete="off" autocorrect="off" spellcheck="false"
              @focus="focused = true" @blur="focused = false"
              @keydown.enter="doAction"
              :disabled="loading"
            />
            <button v-if="inputUrl" class="si-clear" @click="clearInput"><X :size="13"/></button>
            <button class="si-paste" @click="paste" title="Coller"><Clipboard :size="13"/></button>
          </div>

          <!-- Options -->
          <div class="search-opts">
            <div class="opt-group">
              <span class="opt-lbl">{{ mode === 'playlist' ? 'Limite' : 'Qualité' }}</span>
              <div class="opt-chips">
                <template v-if="mode === 'single'">
                  <button v-for="q in qualities" :key="q.id"
                    :class="['ochip', { 'ochip--on': selectedQuality === q.id }]"
                    @click="selectedQuality = q.id">{{ q.label }}</button>
                </template>
                <template v-else>
                  <button v-for="n in [10,20,30,50]" :key="n"
                    :class="['ochip', { 'ochip--on': playlistLimit === n }]"
                    @click="playlistLimit = n">{{ n }}</button>
                </template>
              </div>
            </div>

            <button class="go-btn" :disabled="!inputUrl.trim() || loading" @click="doAction">
              <Loader2 v-if="loading" :size="15" class="spin" />
              <DownloadCloud v-else :size="15" />
              {{ loading ? 'Analyse…' : mode === 'playlist' ? 'Charger' : 'Extraire' }}
            </button>
          </div>
        </div>

        <!-- Stats bar -->
        <div class="stats-bar">
          <span><strong>16</strong> plateformes</span>
          <span class="sep">·</span>
          <span><strong>4K</strong> max</span>
          <span class="sep">·</span>
          <span><strong>No</strong> watermark</span>
          <span class="sep">·</span>
          <span><strong>MP3</strong> audio</span>
        </div>
      </div>
    </section>

    <!-- ══ RÉSULTATS ══════════════════════════════════════════════════════════ -->
    <section v-if="loading || result || playlist || errorMsg" class="results-section">
      <div class="container">

        <!-- Loading -->
        <div v-if="loading" class="loading-wrap">
          <div class="loading-track"><div class="loading-bar"></div></div>
          <p>Extraction en cours…</p>
        </div>

        <!-- Error -->
        <transition name="fu">
          <div v-if="errorMsg && !loading" class="err-bar">
            <AlertCircle :size="14"/>
            <span>{{ errorMsg }}</span>
            <button @click="errorMsg=null"><X :size="12"/></button>
          </div>
        </transition>

        <!-- ── Résultat vidéo unique ── -->
        <transition name="fu">
          <div v-if="result && !loading" class="result-wrap">

            <!-- Thumbnail côté gauche -->
            <div v-if="result.thumbnail" class="res-thumb">
              <img :src="result.thumbnail" :alt="result.title" loading="lazy"/>
              <div class="res-thumb__bar">
                <span class="res-plat">{{ result.platform }}</span>
                <span v-if="result.duration" class="res-dur"><Clock :size="9"/> {{ fmt(result.duration) }}</span>
              </div>
            </div>

            <!-- Infos côté droit -->
            <div class="res-info">
              <div class="res-head">
                <div>
                  <h3 class="res-title">{{ result.title }}</h3>
                  <p v-if="result.author" class="res-author"><UserRound :size="11"/> {{ result.author }}</p>
                </div>
                <div v-if="result.view_count||result.like_count" class="res-meta">
                  <span v-if="result.view_count"><Eye :size="10"/> {{ fmtN(result.view_count) }}</span>
                  <span v-if="result.like_count"><Heart :size="10"/> {{ fmtN(result.like_count) }}</span>
                </div>
              </div>

              <div v-if="result.platform==='tiktok'" class="nowm-tag">
                <ShieldCheck :size="12"/> Sans watermark TikTok
              </div>

              <div class="res-actions">
                <a :href="result.proxy_download_url || dlUrl(result.no_watermark_url||result.best_url, result.title)"
                   :download="safe(result.title)+'.mp4'" class="btn-dl" @click="onDl(result)">
                  <DownloadCloud :size="14"/>
                  Télécharger {{ result.platform==='tiktok' ? 'sans WM' : '' }}
                </a>
                <div class="res-sec-row">
                  <a v-if="ffmpeg && stripUrl(result)!='#'"
                     :href="stripUrl(result)" :download="safe(result.title)+'_clean.mp4'"
                     class="btn-sec" @click="onDl(result)">
                    <ShieldOff :size="12"/> Sans métadonnées
                  </a>
                  <a v-if="result.audio_only_url"
                     :href="dlUrl(result.audio_only_url, result.title+'_audio')"
                     :download="safe(result.title)+'.mp3'" class="btn-sec">
                    <Music :size="12"/> Audio MP3
                  </a>
                </div>
              </div>

              <!-- Formats -->
              <div v-if="result.formats?.length>1" class="fmts-wrap">
                <button class="fmts-toggle" @click="showFmts=!showFmts">
                  <Layers :size="11"/> {{ result.formats.length }} formats disponibles
                  <ChevronDown :size="11" :class="{flip:showFmts}"/>
                </button>
                <transition name="drop">
                  <div v-if="showFmts" class="fmts-list">
                    <a v-for="f in [...result.formats].reverse()" :key="f.format_id"
                       :href="f.proxy_url||dlUrl(f.url,result.title)"
                       :download="`${safe(result.title)}_${f.quality||f.format_id}.${f.ext}`"
                       class="fmt-row">
                      <span class="fmt-q">{{ f.height ? f.height+'p' : f.quality }}</span>
                      <span class="fmt-e">{{ f.ext }}</span>
                      <span v-if="f.filesize" class="fmt-s">{{ fmtSz(f.filesize) }}</span>
                      <span v-if="f.no_watermark" class="fmt-wm">No WM</span>
                      <Download :size="11"/>
                    </a>
                  </div>
                </transition>
              </div>
            </div>
          </div>
        </transition>

        <!-- ── Playlist ── -->
        <transition name="fu">
          <div v-if="playlist && !loading" class="pl-wrap">
            <div class="pl-head">
              <div class="pl-head__left">
                <List :size="14" class="pl-icon"/>
                <div>
                  <p class="pl-title">{{ playlist.playlist_title }}</p>
                  <p class="pl-sub">{{ playlist.items.filter(i=>i.success).length }} / {{ playlist.items.length }} extraites</p>
                </div>
              </div>
              <button class="btn-dl btn-dl--sm" @click="dlAll">
                <DownloadCloud :size="13"/> Tout télécharger
              </button>
            </div>
            <div class="pl-items">
              <div v-for="item in playlist.items" :key="item.index"
                   :class="['pl-row',{'pl-row--fail':!item.success}]">
                <span class="pl-n">{{ item.index+1 }}</span>
                <div class="pl-inf">
                  <p class="pl-t">{{ item.data?.title||item.error||'—' }}</p>
                  <p v-if="item.data?.duration||item.data?.author" class="pl-m">
                    <span v-if="item.data?.author">{{ item.data.author }}</span>
                    <span v-if="item.data?.duration"> · {{ fmt(item.data.duration) }}</span>
                  </p>
                </div>
                <a v-if="item.success&&item.data"
                   :href="item.data.proxy_download_url||dlUrl(item.data.no_watermark_url||item.data.best_url,item.data.title)"
                   :download="safe(item.data.title)+'.mp4'" class="pl-btn" @click="onDl(item.data)">
                  <Download :size="13"/>
                </a>
                <AlertCircle v-else :size="13" class="pl-err"/>
              </div>
            </div>
          </div>
        </transition>

      </div>
    </section>

    <!-- ══ PLATEFORMES (cartes défilantes) ══════════════════════════════════ -->
    <section class="plats-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">Plateformes supportées</h2>
          <p class="section-sub">Colle n'importe quel lien — WaziScope détecte automatiquement.</p>
        </div>
      </div>

      <div class="plats-track-wrap">
        <div class="plats-track">
          <div v-for="p in platformCards" :key="p.id" class="plat-card">
            <div :class="['plat-card__icon', `pc-${p.id}`]">
              <component :is="platformIcon(p.id)" :size="20"/>
            </div>
            <p class="plat-card__name">{{ p.name }}</p>
            <p class="plat-card__feat">{{ p.feat }}</p>
            <span v-if="p.badge" class="plat-card__badge">{{ p.badge }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ══ FONCTIONNALITÉS ════════════════════════════════════════════════════ -->
    <section class="feats-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">Pourquoi WaziScope ?</h2>
        </div>
        <div class="feats-grid">
          <div v-for="f in features" :key="f.title" class="feat-card">
            <div class="feat-icon"><component :is="f.icon" :size="20"/></div>
            <h4>{{ f.title }}</h4>
            <p>{{ f.desc }}</p>
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
  Video, Tv2, Radio, PlaySquare, Globe, Rss, Music2,
} from 'lucide-vue-next'

const route  = useRoute()
const notify = inject('notify', () => {})

// ─── State ───────────────────────────────────────────────────────────────────
const inputUrl         = ref('')
const inputEl          = ref(null)
const focused          = ref(false)
const loading          = ref(false)
const result           = ref(null)
const playlist         = ref(null)
const errorMsg         = ref(null)
const showFmts         = ref(false)
const ffmpeg           = ref(false)
const mode             = ref('single')
const selectedQuality  = ref('best')
const playlistLimit    = ref(20)

const qualities = [
  { id:'best', label:'Auto' }, { id:'4k', label:'4K' },
  { id:'1080', label:'1080p' }, { id:'720', label:'720p' },
  { id:'480', label:'480p' }, { id:'audio', label:'Audio' },
]

// ─── Platform cards ───────────────────────────────────────────────────────────
const platformCards = [
  { id:'tiktok',      name:'TikTok',       feat:'Sans watermark',      badge:'No WM' },
  { id:'youtube',     name:'YouTube',      feat:'4K · Playlists',      badge:'4K' },
  { id:'instagram',   name:'Instagram',    feat:'Reels · Stories',     badge:null },
  { id:'facebook',    name:'Facebook',     feat:'Vidéos · Reels',      badge:null },
  { id:'twitter',     name:'Twitter / X',  feat:'Tweets vidéo',        badge:null },
  { id:'pinterest',   name:'Pinterest',    feat:'Épingles vidéo',      badge:null },
  { id:'linkedin',    name:'LinkedIn',     feat:'Vidéos natives',      badge:null },
  { id:'vimeo',       name:'Vimeo',        feat:'HD · Playlists',      badge:'HD' },
  { id:'dailymotion', name:'Dailymotion',  feat:'Playlists',           badge:null },
  { id:'twitch',      name:'Twitch',       feat:'Clips · VODs',        badge:null },
  { id:'rumble',      name:'Rumble',       feat:'Longue durée',        badge:null },
  { id:'odysee',      name:'Odysee',       feat:'Open source',         badge:null },
  { id:'snapchat',    name:'Snapchat',     feat:'Spotlight',           badge:null },
  { id:'bilibili',    name:'Bilibili',     feat:'Anime · Musique',     badge:null },
]

const platformIcon = id => ({
  tiktok:Music2, youtube:PlayCircle, pinterest:Bookmark, facebook:Users,
  instagram:Camera, linkedin:Briefcase, twitter:Bird, dailymotion:Video,
  vimeo:Tv2, twitch:Radio, rumble:PlaySquare,
  odysee:Globe, snapchat:Rss, bilibili:Film,
}[id] ?? Film)

const features = [
  { icon:Film,        title:'Longs métrages',        desc:'Films, docs, conférences — aucune limite de durée.' },
  { icon:List,        title:'Playlists entières',     desc:'Jusqu\'à 50 vidéos YouTube/Vimeo d\'un coup.' },
  { icon:ShieldCheck, title:'TikTok sans watermark',  desc:'API mobile officielle, propre, sans logo.' },
  { icon:ShieldOff,   title:'Suppression métadonnées',desc:'GPS, dates, auteur effacés via FFmpeg.' },
  { icon:Music,       title:'Extraction audio MP3',   desc:'Piste audio seule depuis n\'importe quelle vidéo.' },
  { icon:Zap,         title:'Détection auto',         desc:'Colle le lien — la plateforme est reconnue instantanément.' },
]

// ─── Mount ───────────────────────────────────────────────────────────────────
onMounted(async () => {
  const shared = route.query.url || route.query.shared
  if (shared) { inputUrl.value = decodeURIComponent(String(shared)); doAction(); return }
  window.addEventListener('wzs:share', e => { inputUrl.value = e.detail.url; doAction() })
  try {
    const cap = await axios.get('/api/v1/capabilities').catch(() => null)
    if (cap?.data?.ffmpeg !== undefined) ffmpeg.value = cap.data.ffmpeg
  } catch {}
})

// ─── Helpers ─────────────────────────────────────────────────────────────────
const clearInput = () => {
  inputUrl.value = ''; result.value = null; playlist.value = null; errorMsg.value = null
  inputEl.value?.focus()
}

const paste = async () => {
  try {
    const t = await navigator.clipboard.readText()
    if (t?.startsWith('http')) inputUrl.value = t.trim()
  } catch {}
}

const detectMode = url => {
  if (url.toLowerCase().includes('list=')) mode.value = 'playlist'
}

const doAction = () => {
  detectMode(inputUrl.value)
  mode.value === 'playlist' ? doPlaylist() : doExtract()
}

const doExtract = async () => {
  const url = inputUrl.value.trim(); if (!url) return
  loading.value = true; result.value = null; playlist.value = null
  errorMsg.value = null; showFmts.value = false
  try {
    const r = await axios.post('/api/v1/extract', { url, quality: selectedQuality.value })
    if (!r.data.success) { errorMsg.value = r.data.message || 'Extraction échouée'; return }
    result.value = r.data.data
    if (r.data.ffmpeg_available !== undefined) ffmpeg.value = r.data.ffmpeg_available
  } catch (e) {
    errorMsg.value = e.response?.data?.message || 'Erreur serveur'
  } finally { loading.value = false }
}

const doPlaylist = async () => {
  const url = inputUrl.value.trim(); if (!url) return
  loading.value = true; result.value = null; playlist.value = null; errorMsg.value = null
  try {
    const r = await axios.post('/api/v1/extract/playlist', { url, limit: playlistLimit.value })
    if (!r.data.success) { errorMsg.value = r.data.message || 'Playlist échouée'; return }
    playlist.value = r.data
  } catch (e) {
    errorMsg.value = e.response?.data?.message || 'Erreur playlist'
  } finally { loading.value = false }
}

const dlAll = () => {
  playlist.value?.items.filter(i => i.success && i.data).forEach((item, idx) => {
    setTimeout(() => {
      const a = document.createElement('a')
      a.href = item.data.proxy_download_url || dlUrl(item.data.no_watermark_url || item.data.best_url, item.data.title)
      a.download = safe(item.data.title) + '.mp4'; a.click(); onDl(item.data)
    }, idx * 800)
  })
}

const dlUrl = (url, title) =>
  url ? `/api/v1/download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(safe(title)+'.mp4')}` : '#'

const stripUrl = v => {
  const u = v?.no_watermark_url || v?.best_url; if (!u) return '#'
  return `/api/v1/strip?url=${encodeURIComponent(u)}&filename=${encodeURIComponent(safe(v.title))}&platform=${v.platform}`
}

const onDl = v => {
  try {
    const h = JSON.parse(localStorage.getItem('wzs_history') || '[]')
    h.unshift({ id: Date.now(), title: v.title, thumbnail: v.thumbnail, platform: v.platform, url: v.best_url, date: new Date().toISOString() })
    localStorage.setItem('wzs_history', JSON.stringify(h.slice(0, 100)))
  } catch {}
}

const safe   = s => (s||'video').replace(/[^\w\-. ]/g,'_').substring(0,80)
const fmtSz  = b => b>1048576 ? `${(b/1048576).toFixed(1)}MB` : `${(b/1024).toFixed(0)}KB`
const fmtN   = n => n>=1e9?(n/1e9).toFixed(1)+'G':n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':String(n)
const fmt    = s => {
  if (!s) return ''
  const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60)
  return h>0?`${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`:`${m}:${String(sec).padStart(2,'0')}`
}
</script>

<style scoped>
/* ══ HERO ═════════════════════════════════════════════════════════════════════ */
.hero {
  position: relative;
  min-height: 88vh;
  display: flex; align-items: center; justify-content: center;
  text-align: center;
  overflow: hidden;
  padding: 80px 24px 60px;
}

.hero__glow {
  position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 70% 55% at 50% -10%, rgba(27,255,164,0.13) 0%, transparent 70%),
    radial-gradient(ellipse 40% 40% at 80% 80%, rgba(100,60,255,0.08) 0%, transparent 60%);
}

.hero__content {
  position: relative; z-index: 1;
  max-width: 720px; width: 100%;
}

.hero__eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12.5px; font-family: var(--font-mono);
  color: var(--text-md); margin-bottom: 20px;
  letter-spacing: 0.05em; text-transform: uppercase;
}
.dot-pulse {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--mint); box-shadow: 0 0 8px var(--mint);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(.85)} }

.hero__title {
  font-family: var(--font-display);
  font-size: clamp(44px, 9vw, 80px);
  font-weight: 900; line-height: 1.0; letter-spacing: -2.5px;
  margin-bottom: 18px;
}
.hero__accent { color: var(--mint); }

.hero__desc {
  font-size: 15px; color: var(--text-md);
  font-family: var(--font-mono); margin-bottom: 36px;
  line-height: 1.7;
}

/* ── Search block ─────────────────────────────────────────────────────────── */
.search-block {
  background: var(--bg-1);
  border: 1px solid var(--border-md);
  border-radius: 20px;
  padding: 16px 16px 14px;
  text-align: left;
  box-shadow: 0 8px 40px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.04);
}

/* Mode pill */
.mode-pill {
  display: inline-flex; background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 3px; margin-bottom: 12px; gap: 2px;
}
.mpill {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 12px; border-radius: 6px;
  background: none; border: none; cursor: pointer;
  font-size: 12.5px; font-weight: 600; color: var(--text-md);
  font-family: var(--font-body); transition: all 0.15s;
}
.mpill--on { background: var(--bg-2); color: var(--text-hi); }

/* Input */
.search-input {
  display: flex; align-items: center; gap: 8px;
  background: var(--bg); border: 1px solid var(--border-md);
  border-radius: 12px; padding: 12px 14px;
  transition: border-color .18s, box-shadow .18s;
  margin-bottom: 12px;
}
.search-input--focus {
  border-color: var(--mint);
  box-shadow: 0 0 0 3px rgba(27,255,164,.15);
}
.si-icon { color: var(--text-lo); flex-shrink:0; }
.search-input input {
  flex:1; background:none; border:none; outline:none;
  color:var(--text-hi); font-family:var(--font-mono); font-size:13.5px; min-width:0;
}
.search-input input::placeholder { color: var(--text-lo); }
.si-clear, .si-paste {
  background:none; border:none; color:var(--text-lo); cursor:pointer;
  padding:3px; border-radius:5px; display:flex; flex-shrink:0; transition:all .15s;
}
.si-clear:hover,.si-paste:hover { background:var(--bg-2); color:var(--text-hi); }

/* Options row */
.search-opts {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.opt-group { display:flex; align-items:center; gap:7px; flex:1; flex-wrap:wrap; }
.opt-lbl   { font-size:11.5px; font-weight:600; color:var(--text-md); white-space:nowrap; }
.opt-chips { display:flex; gap:4px; flex-wrap:wrap; }
.ochip {
  padding: 4px 10px; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; font-size:12px; font-weight:600; color:var(--text-md);
  cursor:pointer; transition:all .15s;
}
.ochip--on { background:var(--mint-dim); border-color:rgba(27,255,164,.3); color:var(--mint); }
.ochip:hover:not(.ochip--on) { color:var(--text-hi); border-color:var(--border-md); }

.go-btn {
  display:flex; align-items:center; gap:7px;
  padding:10px 22px; background:var(--mint); color:#000;
  border:none; border-radius:10px;
  font-family:var(--font-body); font-size:14px; font-weight:800;
  cursor:pointer; white-space:nowrap; flex-shrink:0;
  transition:opacity .15s,transform .15s; box-shadow:0 4px 16px rgba(27,255,164,.25);
}
.go-btn:hover:not(:disabled) { opacity:.88; transform:translateY(-1px); }
.go-btn:disabled { opacity:.35; cursor:not-allowed; box-shadow:none; }

/* Stats bar */
.stats-bar {
  display: flex; align-items: center; justify-content: center;
  gap: 10px; margin-top: 20px;
  font-size: 12.5px; color: var(--text-lo); font-family: var(--font-mono);
}
.stats-bar strong { color: var(--text-md); }
.sep { color: var(--border-hi); }

/* ══ RÉSULTATS ════════════════════════════════════════════════════════════════ */
.results-section { padding: 0 0 48px; }

.loading-wrap {
  display:flex; flex-direction:column; align-items:center; gap:12px;
  padding: 40px 0;
}
.loading-track {
  width:260px; height:3px; background:var(--bg-3); border-radius:2px; overflow:hidden;
}
.loading-bar {
  height:100%; border-radius:2px; background:var(--mint);
  animation:slide 1.3s ease-in-out infinite;
  width:40%;
}
@keyframes slide { 0%{transform:translateX(-150%)} 100%{transform:translateX(370%)} }
.loading-wrap p { font-size:13px; color:var(--text-md); font-family:var(--font-mono); }

.err-bar {
  display:flex; align-items:center; gap:8px;
  padding:12px 16px;
  background:rgba(244,63,94,.06); border:1px solid rgba(244,63,94,.2);
  border-radius:12px; color:var(--danger); font-size:13.5px;
  margin-bottom:12px;
}
.err-bar span { flex:1; }
.err-bar button { background:none;border:none;color:var(--text-lo);cursor:pointer;padding:2px;display:flex; }

/* Result */
.result-wrap {
  display:grid; grid-template-columns:320px 1fr; gap:0;
  background:var(--bg-1); border:1px solid var(--border);
  border-radius:20px; overflow:hidden;
}

.res-thumb { position:relative; background:var(--bg-2); }
.res-thumb img { width:100%; height:100%; object-fit:cover; display:block; min-height:200px; }
.res-thumb__bar {
  position:absolute; bottom:0; left:0; right:0;
  background:linear-gradient(to top,rgba(0,0,0,.7) 0%,transparent 100%);
  display:flex; align-items:flex-end; justify-content:space-between;
  padding:10px 12px;
}
.res-plat {
  font-size:11px; font-weight:700; text-transform:capitalize;
  background:rgba(0,0,0,.5); color:#fff;
  padding:2px 8px; border-radius:4px; backdrop-filter:blur(4px);
}
.res-dur {
  display:flex; align-items:center; gap:3px;
  font-size:11px; font-family:var(--font-mono);
  background:rgba(0,0,0,.5); color:#fff;
  padding:2px 7px; border-radius:4px; backdrop-filter:blur(4px);
}

.res-info {
  padding: 22px 22px; display:flex; flex-direction:column; gap:14px;
}
.res-head {
  display:flex; align-items:flex-start; justify-content:space-between; gap:12px;
}
.res-title {
  font-family:var(--font-display); font-size:16px; font-weight:800; line-height:1.3;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
}
.res-author {
  display:flex; align-items:center; gap:4px;
  font-size:12px; color:var(--text-md); margin-top:5px;
}
.res-meta { display:flex; flex-direction:column; gap:4px; flex-shrink:0; }
.res-meta span {
  display:flex; align-items:center; gap:4px;
  font-size:11px; color:var(--text-md); white-space:nowrap;
}

.nowm-tag {
  display:inline-flex; align-items:center; gap:6px;
  padding:5px 12px;
  background:rgba(27,255,164,.08); border:1px solid rgba(27,255,164,.2);
  border-radius:8px; font-size:12.5px; font-weight:700; color:var(--mint);
  width:fit-content;
}

.res-actions { display:flex; flex-direction:column; gap:8px; }
.btn-dl {
  display:flex; align-items:center; justify-content:center; gap:7px;
  padding:12px 16px; background:var(--mint); color:#000;
  border:none; border-radius:10px;
  font-family:var(--font-body); font-size:14px; font-weight:800;
  cursor:pointer; text-decoration:none;
  transition:opacity .15s,transform .15s;
  box-shadow:0 4px 16px rgba(27,255,164,.2);
}
.btn-dl:hover { opacity:.88; transform:translateY(-1px); }
.btn-dl--sm { padding:8px 14px; font-size:13px; border-radius:8px; }

.res-sec-row { display:flex; gap:7px; flex-wrap:wrap; }
.btn-sec {
  flex:1; min-width:120px;
  display:flex; align-items:center; justify-content:center; gap:5px;
  padding:9px 12px; background:transparent;
  border:1px solid var(--border-md); border-radius:10px;
  color:var(--text-hi); font-size:12.5px; font-weight:600; text-decoration:none;
  transition:all .15s;
}
.btn-sec:hover { background:var(--bg-2); border-color:var(--border-hi); }

/* Formats */
.fmts-wrap { border-top:1px solid var(--border); padding-top:10px; }
.fmts-toggle {
  display:flex; align-items:center; gap:6px;
  background:none; border:none; color:var(--text-md);
  font-size:12px; font-family:var(--font-body); cursor:pointer;
  transition:color .15s; padding:0;
}
.fmts-toggle:hover { color:var(--text-hi); }
.fmts-toggle .flip { transform:rotate(180deg); }
.fmts-toggle svg:last-child { transition:transform .2s; }
.fmts-list { margin-top:8px; border:1px solid var(--border); border-radius:10px; overflow:hidden; }
.fmt-row {
  display:flex; align-items:center; gap:8px; padding:8px 12px;
  text-decoration:none; color:var(--text-hi); font-size:12.5px;
  border-bottom:1px solid var(--border); transition:background .12s;
}
.fmt-row:last-child { border:none; }
.fmt-row:hover { background:var(--bg-2); }
.fmt-q  { font-weight:800; width:42px; }
.fmt-e  { font-family:var(--font-mono); font-size:11px; color:var(--text-md); }
.fmt-s  { font-size:11px; color:var(--text-md); margin-left:auto; }
.fmt-wm { font-size:9px; font-weight:800; background:var(--mint); color:#000; padding:1px 5px; border-radius:3px; }

/* Playlist */
.pl-wrap {
  background:var(--bg-1); border:1px solid var(--border);
  border-radius:20px; overflow:hidden;
}
.pl-head {
  display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:16px 20px; background:var(--bg-2); border-bottom:1px solid var(--border);
  flex-wrap:wrap;
}
.pl-head__left { display:flex; align-items:center; gap:12px; flex:1; min-width:0; }
.pl-icon  { color:var(--mint); flex-shrink:0; }
.pl-title { font-family:var(--font-display); font-size:15px; font-weight:700; }
.pl-sub   { font-size:12px; color:var(--text-md); margin-top:2px; }
.pl-items { max-height:500px; overflow-y:auto; }
.pl-row {
  display:flex; align-items:center; gap:12px;
  padding:11px 20px; border-bottom:1px solid var(--border); transition:background .12s;
}
.pl-row:last-child { border:none; }
.pl-row:hover { background:var(--bg-2); }
.pl-row--fail { opacity:.4; }
.pl-n  { font-family:var(--font-mono); font-size:11px; color:var(--text-lo); min-width:18px; text-align:right; flex-shrink:0; }
.pl-inf { flex:1; min-width:0; }
.pl-t  { font-size:13px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pl-m  { font-size:11px; color:var(--text-md); margin-top:2px; }
.pl-btn {
  display:flex; align-items:center; justify-content:center;
  width:30px; height:30px; border-radius:8px;
  background:var(--bg); border:1px solid var(--border);
  color:var(--text-md); text-decoration:none; flex-shrink:0; transition:all .15s;
}
.pl-btn:hover { background:var(--mint-dim); border-color:rgba(27,255,164,.3); color:var(--mint); }
.pl-err { color:var(--danger); flex-shrink:0; }

/* ══ SECTIONS COMMUNES ════════════════════════════════════════════════════════ */
.section-header {
  text-align:center; margin-bottom:28px;
}
.section-title {
  font-family:var(--font-display); font-size:clamp(22px,4vw,32px);
  font-weight:800; letter-spacing:-.5px; margin-bottom:8px;
}
.section-sub { font-size:14px; color:var(--text-md); }

/* ══ PLATEFORMES ══════════════════════════════════════════════════════════════ */
.plats-section {
  padding: 60px 0;
  border-top: 1px solid var(--border);
}

.plats-track-wrap {
  overflow-x: auto; scrollbar-width: none;
  padding: 4px 24px 16px;
  cursor: grab;
}
.plats-track-wrap::-webkit-scrollbar { display:none; }

.plats-track {
  display: flex; gap: 12px;
  width: max-content;
  padding: 4px 0;
}

.plat-card {
  flex-shrink: 0; width: 160px;
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: 16px; padding: 18px 16px 16px;
  display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
  transition: all .2s; position: relative;
  cursor: default;
}
.plat-card:hover {
  border-color: var(--border-md);
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0,0,0,.25);
}
.plat-card__icon {
  width:40px; height:40px; border-radius:10px;
  display:flex; align-items:center; justify-content:center;
  background:var(--bg-2); color:var(--text-md);
  transition:all .2s;
}
.plat-card:hover .plat-card__icon { color:var(--text-hi); }
.plat-card__name {
  font-family:var(--font-display); font-size:13.5px; font-weight:800;
}
.plat-card__feat {
  font-size:12px; color:var(--text-md); line-height:1.4;
}
.plat-card__badge {
  position:absolute; top:10px; right:10px;
  font-size:9px; font-weight:800; font-family:var(--font-mono);
  background:var(--mint); color:#000;
  padding:2px 6px; border-radius:4px;
}

/* Platform icon colors on hover */
.pc-tiktok      { background: rgba(0,0,0,.4); }
.pc-youtube     { background: rgba(255,0,0,.08); }
.pc-instagram   { background: rgba(225,48,108,.08); }
.pc-facebook    { background: rgba(24,119,242,.08); }
.pc-twitter     { background: rgba(29,161,242,.08); }
.pc-pinterest   { background: rgba(230,0,35,.08); }
.pc-linkedin    { background: rgba(0,119,181,.08); }
.pc-vimeo       { background: rgba(26,183,234,.08); }
.pc-dailymotion { background: rgba(0,156,255,.08); }
.pc-twitch      { background: rgba(100,65,164,.08); }
.pc-rumble      { background: rgba(133,197,21,.08); }
.pc-odysee      { background: rgba(239,60,50,.08); }
.pc-snapchat    { background: rgba(255,252,0,.08); }
.pc-bilibili    { background: rgba(0,161,214,.08); }

.plat-card:hover .pc-tiktok      { background:rgba(0,0,0,.6);          color:#fff; }
.plat-card:hover .pc-youtube     { background:rgba(255,0,0,.15);       color:#ff4444; }
.plat-card:hover .pc-instagram   { background:rgba(225,48,108,.15);    color:#e1306c; }
.plat-card:hover .pc-facebook    { background:rgba(24,119,242,.15);    color:#1877f2; }
.plat-card:hover .pc-twitter     { background:rgba(29,161,242,.15);    color:#1da1f2; }
.plat-card:hover .pc-pinterest   { background:rgba(230,0,35,.15);      color:#e60023; }
.plat-card:hover .pc-linkedin    { background:rgba(0,119,181,.15);     color:#0077b5; }
.plat-card:hover .pc-vimeo       { background:rgba(26,183,234,.15);    color:#1ab7ea; }
.plat-card:hover .pc-dailymotion { background:rgba(0,156,255,.15);     color:#009cff; }
.plat-card:hover .pc-twitch      { background:rgba(100,65,164,.2);     color:#6441a4; }
.plat-card:hover .pc-rumble      { background:rgba(133,197,21,.15);    color:#85c515; }
.plat-card:hover .pc-odysee      { background:rgba(239,60,50,.15);     color:#ef3c32; }
.plat-card:hover .pc-snapchat    { background:rgba(255,252,0,.12);     color:#fffc00; }
.plat-card:hover .pc-bilibili    { background:rgba(0,161,214,.15);     color:#00a1d6; }

/* ══ FEATURES ═════════════════════════════════════════════════════════════════ */
.feats-section {
  padding: 60px 0 80px;
  border-top: 1px solid var(--border);
}
.feats-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
}
.feat-card {
  background:var(--bg-1); border:1px solid var(--border);
  border-radius:16px; padding:22px 20px; transition:all .2s;
}
.feat-card:hover { border-color:var(--border-md); transform:translateY(-2px); }
.feat-icon {
  width:40px; height:40px; background:var(--mint-dim); border-radius:10px;
  display:flex; align-items:center; justify-content:center;
  color:var(--mint); margin-bottom:14px;
}
.feat-card h4 {
  font-family:var(--font-display); font-size:14.5px; font-weight:800; margin-bottom:6px;
}
.feat-card p { font-size:12.5px; color:var(--text-md); line-height:1.55; }

/* ══ TRANSITIONS ══════════════════════════════════════════════════════════════ */
.fu-enter-active { transition:all .3s cubic-bezier(.34,1.4,.64,1); }
.fu-leave-active { transition:all .18s; }
.fu-enter-from   { opacity:0; transform:translateY(14px) scale(.98); }
.fu-leave-to     { opacity:0; }
.drop-enter-active { transition:all .2s var(--ease); }
.drop-leave-active { transition:all .14s; }
.drop-enter-from   { opacity:0; transform:translateY(-4px); }
.drop-leave-to     { opacity:0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

/* ══ RESPONSIVE ═══════════════════════════════════════════════════════════════ */
@media (max-width: 860px) {
  .result-wrap { grid-template-columns: 1fr; }
  .res-thumb img { min-height: 200px; max-height: 240px; }
  .feats-grid { grid-template-columns: repeat(2,1fr); }
}
@media (max-width: 560px) {
  .hero { min-height: 70vh; }
  .search-opts { flex-wrap: wrap; }
  .go-btn { width:100%; justify-content:center; }
  .feats-grid { grid-template-columns: 1fr; }
  .res-sec-row { flex-direction:column; }
  .btn-sec { flex:unset; width:100%; }
}
</style>
