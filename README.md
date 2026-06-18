# WaziScope

> **Téléchargeur vidéo PWA** — TikTok · YouTube · Pinterest · Facebook · Instagram · LinkedIn · Twitter/X · Dailymotion · Vimeo · Twitch · Rumble · Odysee · Snapchat · Bilibili

[![Laravel](https://img.shields.io/badge/Laravel-13-FF2D20?logo=laravel&logoColor=white)](https://laravel.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-42b883?logo=vue.js&logoColor=white)](https://vuejs.org)
[![PWA](https://img.shields.io/badge/PWA-Share_Target-5A0FC8?logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.03-red)](https://github.com/yt-dlp/yt-dlp)

WaziScope est une **Progressive Web App** qui permet de télécharger des vidéos depuis les apps mobiles en un seul tap via le bouton **"Partager"** de votre téléphone. Installez-la une fois, et elle apparaît dans le menu de partage de toutes vos applications.

**Demo live** : [waziscope.nealix.org](https://waziscope.nealix.org)

---

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│  Client (Vue 3 PWA)                                     │
│  HomeView · HistoryView · Share Target (Service Worker) │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
┌────────────────────────▼────────────────────────────────┐
│  Laravel 13 — API Gateway                               │
│  POST /api/v1/extract   →  proxy vers FastAPI           │
│  GET  /api/v1/download  →  proxy cURL (headers/plateforme) │
│  GET  /api/v1/strip     →  restream sans audio          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP localhost:8032
┌────────────────────────▼────────────────────────────────┐
│  FastAPI (Python) — Extracteur vidéo                    │
│  yt-dlp + scrapers custom par plateforme                │
│  TikTok (tikwm fallback) · Pinterest (HLS→MP4)          │
│  Dailymotion (metadata API) · Facebook · YouTube…       │
└─────────────────────────────────────────────────────────┘
```

---

## Plateformes supportées

| Plateforme  | Statut | Notes                                             |
|-------------|--------|---------------------------------------------------|
| TikTok      | ✅     | Sans watermark · fallback tikwm.com si IP bloquée |
| YouTube     | ✅     | HD jusqu'à 1080p · Playlists                      |
| Pinterest   | ✅     | Scraper HTML · HLS→MP4 automatique                |
| Facebook    | ✅     | Vidéos publiques + Reels                          |
| Instagram   | ⚠️     | Profils publics uniquement (sans login)            |
| LinkedIn    | ✅     | Vidéos natives                                    |
| Twitter / X | ⚠️     | Tweets publics avec vidéo                         |
| Dailymotion | ✅     | Via metadata API (sans impersonation)             |
| Vimeo       | ✅     | HD · Playlists                                    |
| Twitch      | ✅     | Clips · VODs publics                              |
| Rumble      | ✅     | Longue durée                                      |
| Odysee      | ✅     | Open source                                       |
| Snapchat    | ✅     | Spotlight public                                  |
| Bilibili    | ✅     | Anime · Musique                                   |

---

## Fonctionnalités

- **Share Target PWA** — Apparaît dans la liste "Partager" d'Android/iOS après installation
- **TikTok sans watermark** — API mobile TikTok avec fallback [tikwm.com](https://tikwm.com) si l'IP serveur est bloquée
- **Pinterest** — Scraper HTML + conversion automatique HLS (`.m3u8`) → MP4
- **Dailymotion** — Endpoint metadata API direct (contourne l'impersonation Firefox requise par yt-dlp)
- **Proxy de téléchargement** — cURL avec headers spécifiques par plateforme, check HEAD pour URLs expirées
- **Batch extraction** — Jusqu'à 10 URLs en parallèle
- **Historique local** — Statistiques par plateforme, activité hebdomadaire
- **Détection automatique** — Plateforme détectée depuis l'URL
- **Audio seulement** — Bouton MP3 si disponible

---

## Stack

| Couche     | Technologie                                        |
|------------|----------------------------------------------------|
| Frontend   | Vue 3 + Vite + Vue Router                          |
| UI         | CSS custom (dark · mint accent), Lucide icons      |
| Fonts      | Bricolage Grotesque + Outfit + Fira Code           |
| Backend    | Laravel 13 (PHP 8.3)                               |
| Extracteur | FastAPI + yt-dlp + httpx (Python 3.12)             |
| PWA        | Service Worker + Web App Manifest + Share Target   |
| Process    | Supervisor (uvicorn workers)                       |

---

## Installation

### Prérequis

- PHP 8.3+ avec cURL activé
- Composer
- Node.js 20+
- Python 3.12+ (avec venv)

### 1. Cloner

```bash
git clone https://github.com/rogerfarolix/waziscope_wpa.git
cd waziscope_wpa
```

### 2. Extracteur Python (FastAPI)

```bash
cd extractor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Lancer (dev)
uvicorn main:app --host 127.0.0.1 --port 8032 --reload
```

**Supervisor (production)** — `/etc/supervisor/conf.d/waziscope-extractor.conf` :

```ini
[program:waziscope-extractor]
command=/path/to/extractor/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8032 --workers 2
directory=/path/to/extractor
user=deploy
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/waziscope-extractor.err.log
stdout_logfile=/var/log/supervisor/waziscope-extractor.out.log
```

### 3. Backend Laravel

```bash
cd laravel
composer install --no-dev --optimize-autoloader
cp .env.example .env
php artisan key:generate

# .env — ajouter :
# WAZISCOPE_EXTRACTOR_URL=http://127.0.0.1:8032

php artisan migrate
php artisan config:cache && php artisan route:cache
```

`config/services.php` :

```php
'waziscope' => [
    'extractor_url' => env('WAZISCOPE_EXTRACTOR_URL', 'http://127.0.0.1:8032'),
],
```

### 4. Frontend Vue 3

```bash
cd laravel
npm ci
npm run build
```

### 5. Déploiement automatique

Un script `deploy.sh` est fourni à la racine du projet. Il gère git pull, composer, npm build, artisan cache, pip sync et redémarrage supervisor en une commande :

```bash
bash deploy.sh
```

---

## Routes API

```text
GET  /api/v1/health              — État Laravel + FastAPI + ffmpeg
GET  /api/v1/capabilities        — Capacités serveur
GET  /api/v1/platforms           — Plateformes supportées
GET  /api/v1/detect?url=         — Détecter la plateforme sans extraire
POST /api/v1/extract             — Extraire une vidéo { "url": "..." }
POST /api/v1/extract/batch       — Batch { "urls": [...] }
POST /api/v1/extract/playlist    — Playlist { "url": "...", "limit": 20 }
GET  /api/v1/download?url=&platform=  — Proxy de téléchargement
GET  /api/v1/strip?url=&platform=     — Restream sans audio
```

### Exemple de réponse

```json
{
  "success": true,
  "duration_ms": 980,
  "data": {
    "platform": "tiktok",
    "title": "Titre de la vidéo",
    "author": "username",
    "thumbnail": "https://...",
    "duration": 30.0,
    "best_url": "https://v19.tiktokcdn.com/...",
    "no_watermark_url": "https://v19.tiktokcdn.com/...",
    "proxy_download_url": "https://waziscope.nealix.org/api/v1/download?url=...&platform=tiktok",
    "formats": [...]
  }
}
```

---

## Configuration Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name votre-domaine.com;
    root /var/www/waziscope/laravel/public;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php/php8.3-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
        include fastcgi_params;
    }

    location /sw.js {
        add_header Cache-Control "no-cache";
        try_files $uri /index.php?$query_string;
    }
}
```

---

## Résolution de bugs courants

**Fichier téléchargé nommé `video.mp4.json`**
L'URL CDN a expiré (TikTok expire les CDNs en quelques minutes). Ré-extraire la vidéo.

**TikTok — status code 0**
L'IP serveur est bloquée par TikTok. Le fallback tikwm.com prend le relais automatiquement.

**Pinterest — titre générique**
yt-dlp peut renvoyer "." comme titre. Le scraper HTML de secours (`_extract_pinterest_title`) récupère le vrai titre depuis les balises og:title / seo_title.

**Dailymotion — impersonation error**
yt-dlp 2026 nécessite Firefox pour Dailymotion. WaziScope utilise l'endpoint metadata API direct en fallback.

**Mise à jour yt-dlp** (à faire régulièrement) :

```bash
venv/bin/pip install -U yt-dlp
sudo supervisorctl restart waziscope-extractor
```

---

## Contribuer

Les PRs sont bienvenues. Pistes d'amélioration :

- [ ] Support Instagram Reels avec cookies
- [ ] Téléchargement en arrière-plan (Background Sync API)
- [ ] Authentification utilisateur + quotas
- [ ] Support Snapchat Spotlight amélioré

---

## Licence

MIT — voir [LICENSE](LICENSE)

---

## Avertissement

WaziScope est destiné au téléchargement de contenu dont vous êtes l'auteur ou pour lequel vous disposez des droits nécessaires. L'utilisation pour du contenu protégé par des droits d'auteur sans autorisation relève de la responsabilité de l'utilisateur.

---

*Développé par [Roger Gnanih](https://roger.nealix.org) · Nealix · Bénin*
