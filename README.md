# WaziScope

> **Téléchargeur vidéo PWA** : TikTok · Instagram · Pinterest · LinkedIn · Dailymotion · Twitch · Odysee · Weibo, et prise en charge partielle de YouTube, Facebook, Twitter/X, Vimeo, Rumble, Snapchat et Bilibili (voir [Limites actuelles](#limites-actuelles)).

[![Laravel](https://img.shields.io/badge/Laravel-13-FF2D20?logo=laravel&logoColor=white)](https://laravel.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-42b883?logo=vue.js&logoColor=white)](https://vuejs.org)
[![PWA](https://img.shields.io/badge/PWA-Share_Target-5A0FC8?logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.10-red)](https://github.com/yt-dlp/yt-dlp)

WaziScope est une **Progressive Web App** qui permet de télécharger des vidéos depuis les apps mobiles en un seul tap via le bouton **« Partager »** du téléphone. Une fois installée, elle apparaît dans le menu de partage de toutes les applications.

**Démo** : [waziscope.nealix.org](https://waziscope.nealix.org)

---

## Plateformes supportées

> État mesuré en production le **07/11/2026**. Il est revérifié chaque heure par `extractor/smoke_test.py`, qui envoie un mail à chaque changement. L'état en direct est affiché sur la page d'accueil (badge « Indisponible ») et exposé par `GET /api/v1/status`.

| Plateforme  | Statut | Détail |
|-------------|--------|--------|
| TikTok      | ✅ | Sans watermark · secours via tikwm.com |
| Instagram   | ✅ | Reels et posts publics (impersonation navigateur `curl_cffi`) |
| Pinterest   | ✅ | Scraper HTML · conversion HLS → MP4 |
| LinkedIn    | ✅ | Vidéos natives des posts publics |
| Dailymotion | ✅ | Via l'API metadata |
| Twitch      | ✅ | Clips et VOD publiques |
| Odysee      | ✅ | Liens `odysee.com` / `lbry.tv` |
| Weibo       | ✅ | |
| YouTube     | ❌ | IP du serveur bloquée (« Sign in to confirm you're not a bot ») · proxy résidentiel requis |
| Rumble      | ❌ | IP du serveur bloquée (HTTP 403) · proxy résidentiel requis |
| Vimeo       | ❌ | IP du serveur bloquée / connexion exigée · proxy résidentiel requis |
| Bilibili    | ⚠️ | Anciens liens `av…` OK · liens `BV…` bloqués (HTTP 412) · proxy requis |
| Facebook    | ❌ | Extracteur yt-dlp cassé en amont (« Cannot parse data »), y compris hors serveur |
| Snapchat    | ❌ | Extracteur yt-dlp cassé en amont (« Unable to extract next.js data ») |
| Twitter / X | ⚠️ | « No video could be found » sur les tweets testés · compte connecté probablement requis |

---

## Limites actuelles

### 1. IP datacenter bloquée : YouTube, Rumble, Vimeo, Bilibili

Ces plateformes refusent les requêtes venant des IP d'hébergeurs (Contabo). Les mêmes liens fonctionnent depuis une connexion résidentielle. **La solution est un proxy résidentiel payant**, déjà pris en charge par le code :

```ini
; /etc/supervisor/conf.d/waziscope-extractor.conf
environment=HOME="/home/deploy",USER="deploy",PYTHONPATH="...",WAZISCOPE_PROXY_URL="http://user:pass@host:port"
```

```bash
sudo supervisorctl update
```

`WAZISCOPE_PROXY_PLATFORMS` (par défaut `youtube,rumble,bilibili,vimeo`) choisit les plateformes qui passent par le proxy. Les autres restent en accès direct pour limiter la consommation.

Pour YouTube, le fichier `extractor/youtube_cookies.txt` et le serveur de PO tokens `bgutil` (port 4416) ne suffisent plus depuis l'IP actuelle. Renouveler les cookies (à exporter depuis un compte dédié, pas un compte personnel) peut aider temporairement.

### 2. Extracteurs yt-dlp cassés : Facebook, Snapchat

Ces deux plateformes échouent aussi depuis une IP résidentielle, y compris avec la pré-version de yt-dlp du 04/11/2026. Il faut attendre la correction de yt-dlp. `deploy.sh` installe la dernière version de yt-dlp à chaque déploiement, et le smoke test signale par mail le retour de chaque plateforme.

### 3. Twitter / X

Les tweets testés renvoient « No video could be found », même hors serveur. Il faudra probablement des cookies d'un compte connecté.

### 4. Autres limites

- **Contenus privés, réservés aux membres ou soumis à un âge minimum** : non pris en charge (pas de compte connecté).
- **Liens CDN éphémères** : TikTok et Instagram expirent leurs URL en quelques minutes ; il faut alors relancer l'extraction.
- **Pas de quotas par utilisateur** : seulement une limite de débit par IP (30 extractions/min, 5 batch/min, 60 téléchargements/min).
- **Progression d'extraction** (`/extract/progress`) stockée en mémoire : perdue au redémarrage et non partagée entre les 2 workers uvicorn.

---

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│  Client : Vue 3 PWA                                      │
│  HomeView · HistoryView · Share Target (Service Worker)  │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTPS (Nginx système + PHP-FPM 8.3)
┌───────────────────────────▼──────────────────────────────┐
│  Laravel 13 : passerelle API + en-têtes de sécurité (CSP) │
│  /api/v1/extract  → extracteur                           │
│  /api/v1/download → proxy cURL (domaines CDN autorisés)  │
│  /api/v1/strip    → ffmpeg : suppression des métadonnées │
│  /api/v1/status   → état des plateformes (cache 5 min)   │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP 127.0.0.1:8032 (Supervisor)
┌───────────────────────────▼──────────────────────────────┐
│  FastAPI : extracteur (extractor/)                       │
│  main.py        routes + aiguillage par plateforme       │
│  wz/core.py     config, schémas, options yt-dlp, proxy   │
│  wz/tiktok.py · pinterest.py · facebook.py ·             │
│  dailymotion.py · youtube.py (Invidious en secours)      │
│  smoke_test.py  test réel horaire → .smoke_state.json    │
└──────────────────────────────────────────────────────────┘
```

| Couche     | Technologie |
|------------|-------------|
| Frontend   | Vue 3 + Vite + Vue Router · Lucide icons |
| Backend    | Laravel 13 (PHP 8.3) |
| Extracteur | FastAPI + yt-dlp + curl_cffi + httpx (Python 3.12) |
| JS runtime | Node (YouTube EJS) · Deno via pip |
| YouTube    | bgutil PO token provider · cookies · secours Invidious |
| PWA        | Service Worker + Web App Manifest + Share Target |
| Process    | Supervisor (2 workers uvicorn) · pas de Docker |

---

## Installation

Prérequis : PHP 8.3+ avec cURL, Composer, Node.js 20+, Python 3.12+, ffmpeg (pour `/strip`).

```bash
git clone https://github.com/rogerfarolix/waziscope_wpa.git
cd waziscope_wpa

# Extracteur
cd extractor
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/uvicorn main:app --host 127.0.0.1 --port 8032 --reload

# Laravel + front
cd ../laravel
composer install
cp .env.example .env && php artisan key:generate
# .env : WAZISCOPE_EXTRACTOR_URL=http://127.0.0.1:8032
php artisan migrate
npm ci && npm run build
```

En local (`APP_ENV=local`), la CSP est désactivée pour permettre le rechargement à chaud de Vite.

---

## Production

La prod (`/var/www/Projets/nealix/waziscope_wpa`) tourne **sans Docker** : Nginx système, PHP-FPM 8.3, extracteur sous Supervisor (`waziscope-extractor`).

```bash
bash deploy.sh
```

Le script enchaîne : `git pull`, Composer, build npm, cache artisan, dépendances pip, mise à jour de yt-dlp, redémarrage de Supervisor, rechargement de PHP-FPM, **tests unitaires, health check (échec = déploiement en erreur) et smoke test rapide**.

Tâches cron (utilisateur `deploy`) :

| Fréquence | Tâche |
|-----------|-------|
| Toutes les heures | `smoke_test.py --mail` : extraction réelle par plateforme, mail si l'état change, met à jour `/status` |
| Quotidienne 9h | `run_cookie_check.sh` : expiration des cookies YouTube |

Variables de l'extracteur : `WAZISCOPE_PROXY_URL`, `WAZISCOPE_PROXY_PLATFORMS` (voir [Limites actuelles](#limites-actuelles)).

---

## Routes API

```text
GET  /api/v1/health              État Laravel + extracteur + ffmpeg
GET  /api/v1/capabilities        Capacités serveur (ffmpeg…)
GET  /api/v1/platforms           Plateformes connues
GET  /api/v1/status              État par plateforme (dernier smoke test)
GET  /api/v1/detect?url=         Détecter la plateforme sans extraire
POST /api/v1/extract             { "url": "...", "quality": "best|1080|720|480|audio" }
POST /api/v1/extract/batch       { "urls": [...] } (10 max)
POST /api/v1/extract/playlist    { "url": "...", "limit": 20 } (50 max)
GET  /api/v1/download?url=&platform=   Proxy de téléchargement (CDN autorisés uniquement)
GET  /api/v1/strip?url=&platform=      Téléchargement sans métadonnées (ffmpeg)
```

Les erreurs sont renvoyées en français lisible, par exemple `"Rumble bloque temporairement notre serveur. Réessayez plus tard."`.

---

## Tests

```bash
cd extractor && venv/bin/python -m pytest tests   # détection, erreurs, proxy (sans réseau)
cd laravel && php artisan test                    # anti-SSRF du proxy, CSP, /status
venv/bin/python extractor/smoke_test.py           # tests réels sur chaque plateforme
venv/bin/python extractor/smoke_test.py --only tiktok,instagram
```

---

## Dépannage

**Une plateforme passe en « Indisponible »** : lancer `smoke_test.py --only <plateforme>` puis lire `/var/log/supervisor/waziscope-extractor.err.log`. « 403 / 412 / not a bot / blocked » indique une IP bloquée (proxy requis). « Cannot parse / Unable to extract » indique un extracteur cassé en amont (attendre une mise à jour de yt-dlp).

**Fichier téléchargé nommé `video.mp4.json`** : l'URL CDN a expiré. Relancer l'extraction.

**TikTok, code 0** : IP bloquée par TikTok. Le secours tikwm.com prend le relais automatiquement.

**Mettre à jour yt-dlp manuellement** :

```bash
extractor/venv/bin/pip install -U yt-dlp && sudo supervisorctl restart waziscope-extractor
```

**`deploy.sh: Permission denied`** : le bit exécutable a été perdu (commit depuis Windows). Lancer `bash deploy.sh`, puis `git update-index --chmod=+x deploy.sh`.

---

## Feuille de route

- [ ] Proxy résidentiel pour YouTube, Rumble, Vimeo et Bilibili
- [ ] Retour de Facebook et Snapchat (à surveiller dans les mises à jour de yt-dlp)
- [ ] Twitter/X et Instagram privés via cookies d'un compte dédié
- [ ] Progression d'extraction partagée entre workers (Redis)
- [ ] Authentification utilisateur et quotas
- [ ] Téléchargement en arrière-plan (Background Sync API)

---

## Avertissement

WaziScope est destiné au téléchargement de contenu dont vous êtes l'auteur ou pour lequel vous disposez des droits nécessaires. Respecter les conditions d'utilisation des plateformes et le droit d'auteur relève de la responsabilité de l'utilisateur.

---

*Développé par [Roger Gnanih](https://roger.nealix.org) · Nealix · Bénin*
