<template>
  <div class="guide-page">

    <!-- ── Hero ─────────────────────────────────────────────────────────────── -->
    <section class="guide-hero">
      <div class="guide-hero__glow" aria-hidden="true"></div>
      <div class="guide-hero__inner">
        <div class="guide-hero__badge">
          <Smartphone :size="13"/> Partager en 1 tap
        </div>
        <h1 class="guide-hero__title">
          Utiliser WaziScope<br>
          <span class="accent">depuis vos apps</span>
        </h1>
        <p class="guide-hero__sub">
          Téléchargez directement depuis TikTok, Pinterest ou YouTube
          sans quitter l'app — en moins de 10 secondes.
        </p>
      </div>
    </section>

    <!-- ── Onglets ────────────────────────────────────────────────────────── -->
    <div class="os-tabs container">
      <button :class="['os-tab', { 'os-tab--on': tab === 'ios' }]" @click="tab='ios'">
        <span class="os-tab__icon">🍎</span> iPhone (iOS)
      </button>
      <button :class="['os-tab', { 'os-tab--on': tab === 'android' }]" @click="tab='android'">
        <span class="os-tab__icon">🤖</span> Android
      </button>
    </div>

    <!-- ══ IOS ══════════════════════════════════════════════════════════════ -->
    <section v-if="tab === 'ios'" class="guide-section container">

      <div class="tip-box tip-box--info">
        <Info :size="15"/>
        <p>Apple n'autorise pas les sites web à s'ajouter dans le menu Partager natif.
        La solution : créer un <strong>Raccourci iOS</strong> en 2 minutes — il apparaît
        ensuite dans toutes vos apps.</p>
      </div>

      <!-- Option rapide -->
      <div class="quick-box">
        <div class="quick-box__left">
          <Zap :size="18" class="quick-icon"/>
          <div>
            <p class="quick-title">Option rapide — URL copiée</p>
            <p class="quick-desc">Sur TikTok/Pinterest, appuie sur <strong>Copier le lien</strong>,
            puis reviens sur WaziScope. L'URL est collée automatiquement.</p>
          </div>
        </div>
        <router-link to="/" class="wz-btn wz-btn--mint wz-btn--sm">
          Ouvrir l'app
        </router-link>
      </div>

      <!-- Séparateur -->
      <div class="or-sep"><span>ou créer un Raccourci (1 fois)</span></div>

      <!-- Étapes -->
      <div class="steps">

        <div class="step">
          <div class="step__num">1</div>
          <div class="step__body">
            <h3 class="step__title">Ouvrir l'app Raccourcis</h3>
            <p class="step__desc">Cherche <strong>Raccourcis</strong> sur ton iPhone ou utilise
            le bouton ci-dessous.</p>
            <a href="shortcuts://" class="wz-btn wz-btn--outline wz-btn--sm step__cta">
              <Smartphone :size="13"/> Ouvrir Raccourcis
            </a>
          </div>
          <div class="step__illus step__illus--app">
            <div class="mock-icon mock-icon--shortcuts">
              <div class="si-grid">
                <span></span><span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="step">
          <div class="step__num">2</div>
          <div class="step__body">
            <h3 class="step__title">Créer un nouveau raccourci</h3>
            <p class="step__desc">Appuie sur le <strong>+</strong> en haut à droite, puis
            sur <strong>Ajouter une action</strong>.</p>
          </div>
          <div class="step__illus">
            <div class="mock-btn mock-btn--plus">+</div>
          </div>
        </div>

        <div class="step">
          <div class="step__num">3</div>
          <div class="step__body">
            <h3 class="step__title">Chercher « Ouvrir l'URL »</h3>
            <p class="step__desc">Dans la barre de recherche d'actions, tape
            <code>URL</code> et sélectionne <strong>Ouvrir l'URL</strong>.</p>
          </div>
          <div class="step__illus">
            <div class="mock-search">
              <Search :size="12"/><span>URL</span>
            </div>
          </div>
        </div>

        <div class="step">
          <div class="step__num">4</div>
          <div class="step__body">
            <h3 class="step__title">Saisir l'URL de WaziScope</h3>
            <p class="step__desc">Dans le champ URL, tape l'adresse ci-dessous,
            puis appuie après le <code>=</code> et choisis
            <strong>Saisie du raccourci</strong> (variable bleue).</p>
            <div class="url-block">
              <code class="url-code">https://waziscope.nealix.org?url=<span class="url-var">▸</span></code>
              <button class="copy-btn" @click="copyUrl">
                <Copy :size="12"/>
                {{ copied ? 'Copié !' : 'Copier' }}
              </button>
            </div>
          </div>
        </div>

        <div class="step">
          <div class="step__num">5</div>
          <div class="step__body">
            <h3 class="step__title">Activer « Feuille de partage »</h3>
            <p class="step__desc">Appuie sur <strong>⋯</strong> (options) en haut à droite →
            active <strong>Afficher dans la feuille de partage</strong> et nomme
            le raccourci <strong>WaziScope</strong>.</p>
          </div>
          <div class="step__illus">
            <div class="mock-toggle">
              <span>Feuille de partage</span>
              <div class="mock-toggle__sw mock-toggle__sw--on"></div>
            </div>
          </div>
        </div>

        <div class="step step--final">
          <div class="step__num step__num--done"><CheckCircle2 :size="16"/></div>
          <div class="step__body">
            <h3 class="step__title">C'est prêt !</h3>
            <p class="step__desc">Sur TikTok ou Pinterest, appuie sur
            <strong>Partager</strong> → <strong>WaziScope</strong>. Safari s'ouvre et
            le téléchargement démarre automatiquement.</p>
          </div>
        </div>

      </div>
    </section>

    <!-- ══ ANDROID ══════════════════════════════════════════════════════════ -->
    <section v-if="tab === 'android'" class="guide-section container">

      <div class="tip-box tip-box--success">
        <CheckCircle2 :size="15"/>
        <p><strong>Sur Android, c'est automatique</strong> une fois l'app installée.
        WaziScope s'inscrit lui-même dans le menu Partager de toutes vos apps.</p>
      </div>

      <div class="steps">

        <div class="step">
          <div class="step__num">1</div>
          <div class="step__body">
            <h3 class="step__title">Ouvrir WaziScope dans Chrome</h3>
            <p class="step__desc">Visite <strong>waziscope.nealix.org</strong> depuis
            Google Chrome sur Android.</p>
            <a href="/" class="wz-btn wz-btn--mint wz-btn--sm step__cta">
              Ouvrir WaziScope
            </a>
          </div>
        </div>

        <div class="step">
          <div class="step__num">2</div>
          <div class="step__body">
            <h3 class="step__title">Installer l'app</h3>
            <p class="step__desc">Chrome affiche une bannière <strong>"Installer"</strong>
            en bas de l'écran. Ou appuie sur <strong>⋮ → Ajouter à l'écran d'accueil</strong>.</p>
          </div>
          <div class="step__illus">
            <div class="mock-install">
              <div class="mock-install__icon">W</div>
              <div>
                <p>WaziScope</p>
                <p class="mock-install__sub">waziscope.nealix.org</p>
              </div>
              <div class="mock-install__btn">Installer</div>
            </div>
          </div>
        </div>

        <div class="step">
          <div class="step__num">3</div>
          <div class="step__body">
            <h3 class="step__title">Partager depuis n'importe quelle app</h3>
            <p class="step__desc">Sur TikTok, Pinterest ou YouTube, appuie sur
            <strong>Partager</strong> et sélectionne <strong>WaziScope</strong>
            dans la liste.</p>
          </div>
        </div>

        <div class="step step--final">
          <div class="step__num step__num--done"><CheckCircle2 :size="16"/></div>
          <div class="step__body">
            <h3 class="step__title">Téléchargement automatique</h3>
            <p class="step__desc">WaziScope s'ouvre et lance l'extraction immédiatement.
            Aucune manipulation supplémentaire.</p>
          </div>
        </div>

      </div>
    </section>

    <!-- ── Astuce clipboard ───────────────────────────────────────────────── -->
    <section class="container">
      <div class="clipboard-tip">
        <div class="clipboard-tip__icon"><Clipboard :size="20"/></div>
        <div>
          <p class="clipboard-tip__title">Astuce : Copier le lien</p>
          <p class="clipboard-tip__desc">Sur toutes plateformes, tu peux aussi
          <strong>copier l'URL</strong> de la vidéo, puis ouvrir WaziScope.
          L'app détecte automatiquement l'URL dans ton presse-papier.</p>
        </div>
        <router-link to="/" class="wz-btn wz-btn--ghost wz-btn--sm">
          Essayer →
        </router-link>
      </div>
    </section>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  Smartphone, Info, Zap, CheckCircle2, Search, Copy, Clipboard,
} from 'lucide-vue-next'

const tab    = ref('ios')
const copied = ref(false)

const copyUrl = async () => {
  try {
    await navigator.clipboard.writeText('https://waziscope.nealix.org?url=')
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {}
}
</script>

<style scoped>
.guide-page { padding-bottom: 80px; }

/* ── Hero ─────────────────────────────────────────────────────────────────── */
.guide-hero {
  position: relative; overflow: hidden;
  padding: 64px 24px 48px; text-align: center;
}
.guide-hero__glow {
  position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse 60% 50% at 50% 0%, rgba(27,255,164,.1) 0%, transparent 70%);
}
.guide-hero__inner { position: relative; z-index: 1; max-width: 560px; margin: 0 auto; }
.guide-hero__badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--mint-dim); color: var(--mint);
  border: 1px solid rgba(27,255,164,.2); border-radius: 20px;
  padding: 5px 14px; font-size: 12px; font-weight: 600;
  margin-bottom: 20px; text-transform: uppercase; letter-spacing: .06em;
}
.guide-hero__title {
  font-family: var(--font-display); font-size: clamp(28px, 8vw, 48px);
  font-weight: 800; line-height: 1.1; letter-spacing: -1px; margin-bottom: 16px;
}
.accent { color: var(--mint); }
.guide-hero__sub { font-size: 15px; color: var(--text-md); line-height: 1.6; max-width: 420px; margin: 0 auto; }

/* ── Onglets ──────────────────────────────────────────────────────────────── */
.os-tabs {
  display: flex; gap: 8px; margin: 0 auto 32px;
  padding-top: 0;
}
.os-tab {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 12px 16px; border-radius: var(--r-md);
  background: var(--bg-1); border: 1px solid var(--border);
  color: var(--text-md); font-size: 14px; font-weight: 600;
  cursor: pointer; transition: all .18s var(--ease);
  font-family: var(--font-body);
}
.os-tab--on {
  background: var(--bg-2); border-color: var(--border-hi); color: var(--text-hi);
}
.os-tab__icon { font-size: 17px; }

/* ── Section guide ────────────────────────────────────────────────────────── */
.guide-section { padding-bottom: 40px; }

/* ── Tip box ──────────────────────────────────────────────────────────────── */
.tip-box {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 16px; border-radius: var(--r-md);
  margin-bottom: 24px; font-size: 13.5px; line-height: 1.55;
}
.tip-box--info   { background: rgba(27,255,164,.05); border: 1px solid rgba(27,255,164,.15); color: var(--text-md); }
.tip-box--success{ background: rgba(34,197,94,.06);  border: 1px solid rgba(34,197,94,.2);  color: var(--text-md); }
.tip-box svg { flex-shrink: 0; margin-top: 1px; color: var(--mint); }
.tip-box--success svg { color: var(--success); }

/* ── Quick box ────────────────────────────────────────────────────────────── */
.quick-box {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  background: var(--bg-1); border: 1px solid var(--border-md);
  border-radius: var(--r-lg); padding: 16px;
  margin-bottom: 24px;
}
.quick-box__left { display: flex; align-items: flex-start; gap: 12px; flex: 1; }
.quick-icon { color: var(--mint); flex-shrink: 0; margin-top: 1px; }
.quick-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; color: var(--text-hi); }
.quick-desc  { font-size: 12.5px; color: var(--text-md); line-height: 1.5; }

/* ── Séparateur ───────────────────────────────────────────────────────────── */
.or-sep {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 28px; color: var(--text-lo); font-size: 12px;
}
.or-sep::before, .or-sep::after { content:''; flex:1; height:1px; background:var(--border); }

/* ── Steps ────────────────────────────────────────────────────────────────── */
.steps { display: flex; flex-direction: column; gap: 0; }

.step {
  display: flex; gap: 16px; align-items: flex-start;
  padding: 20px 0;
  border-bottom: 1px solid var(--border);
  position: relative;
}
.step:last-child { border-bottom: none; }
.step--final { padding-top: 24px; }

.step__num {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--bg-2); border: 1px solid var(--border-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: var(--mint);
  flex-shrink: 0; margin-top: 2px;
}
.step__num--done {
  background: rgba(27,255,164,.1); border-color: rgba(27,255,164,.3); color: var(--mint);
}

.step__body { flex: 1; }
.step__title { font-size: 15px; font-weight: 600; color: var(--text-hi); margin-bottom: 6px; }
.step__desc  { font-size: 13.5px; color: var(--text-md); line-height: 1.6; }
.step__cta   { margin-top: 12px; }

.step__illus { flex-shrink: 0; display: flex; align-items: center; }

/* ── URL block ────────────────────────────────────────────────────────────── */
.url-block {
  margin-top: 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.url-code {
  font-family: var(--font-mono); font-size: 12px;
  background: var(--bg); border: 1px solid var(--border-md);
  padding: 8px 12px; border-radius: var(--r-sm); color: var(--text-hi);
  word-break: break-all; line-height: 1.5;
}
.url-var { color: var(--mint); font-weight: 700; }
.copy-btn {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--bg-2); border: 1px solid var(--border-md);
  border-radius: var(--r-sm); padding: 7px 12px;
  font-size: 12px; font-weight: 600; color: var(--text-md);
  cursor: pointer; transition: all .18s; white-space: nowrap;
  font-family: var(--font-body);
}
.copy-btn:hover { color: var(--text-hi); border-color: var(--mint); }

/* ── Mock illustrations ────────────────────────────────────────────────────── */
.mock-icon--shortcuts {
  width: 48px; height: 48px; border-radius: 12px;
  background: linear-gradient(135deg, #2c2ce8, #9b4de8);
  display: flex; align-items: center; justify-content: center;
}
.si-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 4px; padding: 10px;
}
.si-grid span {
  width: 10px; height: 10px; border-radius: 2px;
  background: rgba(255,255,255,.7);
}
.mock-btn--plus {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--mint); color: #000;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 300;
}
.mock-search {
  display: flex; align-items: center; gap: 6px;
  background: var(--bg); border: 1px solid var(--border-md);
  border-radius: 8px; padding: 6px 10px;
  font-size: 12px; color: var(--text-md);
  min-width: 80px;
}
.mock-toggle {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  font-size: 10px; color: var(--text-md); text-align: center; max-width: 72px;
}
.mock-toggle__sw {
  width: 36px; height: 20px; border-radius: 10px; background: var(--bg-3);
  position: relative; transition: background .2s;
}
.mock-toggle__sw--on { background: var(--mint); }
.mock-toggle__sw::after {
  content:''; position: absolute;
  top: 3px; left: 3px; width: 14px; height: 14px;
  border-radius: 50%; background: #fff; transition: left .2s;
}
.mock-toggle__sw--on::after { left: calc(100% - 17px); }

/* ── Android install mock ─────────────────────────────────────────────────── */
.mock-install {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg); border: 1px solid var(--border-md);
  border-radius: var(--r-md); padding: 10px 12px; font-size: 12px;
  color: var(--text-hi); min-width: 0;
}
.mock-install__icon {
  width: 32px; height: 32px; border-radius: 8px;
  background: var(--mint); color: #000;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 14px; flex-shrink: 0;
}
.mock-install__sub { color: var(--text-md); font-size: 10px; margin-top: 1px; }
.mock-install__btn {
  margin-left: auto; background: var(--mint); color: #000;
  border-radius: var(--r-sm); padding: 5px 10px;
  font-weight: 700; font-size: 11px; white-space: nowrap; flex-shrink: 0;
}

/* ── Clipboard tip ────────────────────────────────────────────────────────── */
.clipboard-tip {
  display: flex; align-items: center; gap: 16px;
  background: var(--bg-1); border: 1px solid var(--border-md);
  border-radius: var(--r-lg); padding: 20px;
  margin: 32px 0;
}
.clipboard-tip__icon {
  width: 44px; height: 44px; border-radius: var(--r-md);
  background: var(--mint-dim); color: var(--mint);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.clipboard-tip__title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.clipboard-tip__desc  { font-size: 13px; color: var(--text-md); line-height: 1.5; }

/* ── Mobile ───────────────────────────────────────────────────────────────── */
@media (max-width: 600px) {
  .quick-box { flex-direction: column; align-items: stretch; }
  .quick-box .wz-btn { text-align: center; justify-content: center; }
  .step__illus { display: none; }
  .clipboard-tip { flex-direction: column; text-align: center; }
  .clipboard-tip__icon { margin: 0 auto; }
  .clipboard-tip .wz-btn { text-align: center; justify-content: center; width: 100%; }
}
</style>
