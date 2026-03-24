# WaziScope

> **Téléchargeur vidéo PWA** — TikTok (sans watermark), YouTube, Pinterest, Facebook, Instagram, LinkedIn, Twitter/X

[![Laravel](https://img.shields.io/badge/Laravel-11-FF2D20?logo=laravel&logoColor=white)](https://laravel.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-42b883?logo=vue.js&logoColor=white)](https://vuejs.org)
[![PWA](https://img.shields.io/badge/PWA-Share_Target-5A0FC8?logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.03-red)](https://github.com/yt-dlp/yt-dlp)

WaziScope est une **Progressive Web App** qui permet de télécharger des vidéos depuis les apps mobiles (TikTok, YouTube, Pinterest…) en un seul tap via le bouton **"Partager"** de votre téléphone.

---

## Démonstration

```
App TikTok → Bouton Partager → WaziScope → Téléchargement automatique sans watermark
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Client (Vue 3 PWA)                                             │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐                       │
│  │ HomeView│  │HistoryView│  │ShareView │                       │
│  └────┬────┘  └──────────┘  └────┬─────┘                       │
│       │  Share Target (SW)        │                              │
└───────┼───────────────────────────┼──────────────────────────────┘
        │ HTTP                      │
┌───────▼───────────────────────────▼──────────────────────────────┐
│  Laravel 11 (API)                                                │
│  ┌─────────────────┐  ┌──────────────────┐                      │
│  │ /api/v1/extract  │  │ /api/v1/download │  (proxy cURL)       │
│  └────────┬─────────┘  └──────────────────┘                     │
└───────────┼──────────────────────────────────────────────────────┘
            │ HTTP
┌───────────▼──────────────────────────────────────────────────────┐
│  FastAPI (port 8032) — Service d'extraction                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ yt-dlp + Pinterest HTML scraper                          │   │
│  │ TikTok · YouTube · Pinterest · Facebook                  │   │
│  │ Instagram · LinkedIn · Twitter/X                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Fonctionnalités

- **Share Target PWA** — Apparaît dans la liste "Partager" d'Android/iOS une fois installé
- **TikTok sans watermark** — Via l'API mobile TikTok (app_name: trill)
- **Pinterest** — Scraper HTML intégré (fallback quand l'API yt-dlp est bloquée)
- **YouTube** — HD jusqu'à 1080p (mp4)
- **Facebook, Instagram, LinkedIn, Twitter/X** — Vidéos publiques
- **Proxy de téléchargement** — cURL avec headers spécifiques par plateforme (fix bug `.mp4.json`)
- **Batch extraction** — Jusqu'à 10 URLs en parallèle
- **Historique local** — Stocké dans localStorage
- **Détection automatique** — Détecte la plateforme depuis l'URL
- **Audio seulement** — Bouton MP3 si disponible

---

## Stack

| Couche       | Technologie                              |
|--------------|------------------------------------------|
| Frontend     | Vue 3 + Vite + Vue Router                |
| UI           | CSS custom (shadcn-like), Lucide icons   |
| Fonts        | Bricolage Grotesque + Outfit + Fira Code |
| Backend      | Laravel 11 (PHP 8.2+)                    |
| Extracteur   | FastAPI + yt-dlp (Python 3.11+)          |
| PWA          | Service Worker + Web App Manifest        |

---

## Installation

### Prérequis

- PHP 8.2+ avec cURL activé
- Composer
- Node.js 20+
- Python 3.11+
- pip

---

### 1. Cloner le projet

```bash
git clone https://github.com/rogerfarolix/waziscope_wpa.git
cd waziscope_wpa
```

---

### 2. Service FastAPI (extracteur Python)

```bash
cd extractor

# Installer les dépendances
pip install -r requirements.txt

# Mettre yt-dlp à jour (IMPORTANT — à faire régulièrement)
pip install -U yt-dlp

# Lancer le service
python main.py
# → http://localhost:8032
```

> **Note** : Le service FastAPI doit tourner en arrière-plan. En production, utilisez `supervisor` ou `systemd`.

**Supervisor config (`/etc/supervisor/conf.d/waziscope-extractor.conf`) :**
```ini
[program:waziscope-extractor]
command=uvicorn main:app --host 127.0.0.1 --port 8032 --workers 2
directory=/path/to/waziscope_wpa/extractor
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/waziscope-extractor.err.log
stdout_logfile=/var/log/waziscope-extractor.out.log
```

---

### 3. Backend Laravel

```bash
# Dépendances PHP
composer install

# Configuration
cp .env.example .env
php artisan key:generate

# Configurer .env
# DB_CONNECTION=mysql (ou sqlite pour dev)
# APP_URL=https://votre-domaine.com
```

Ajouter dans `.env` :
```env
WAZISCOPE_EXTRACTOR_URL=http://127.0.0.1:8032
```

Ajouter dans `config/services.php` :
```php
'waziscope' => [
    'extractor_url' => env('WAZISCOPE_EXTRACTOR_URL', 'http://127.0.0.1:8032'),
],
```

```bash
# Migrations (si utilisées)
php artisan migrate

# Cache config
php artisan config:cache
```

---

### 4. Frontend Vue 3

```bash
# Dépendances Node
npm install

# Dépendances supplémentaires requises
npm install vue-router axios lucide-vue-next

# Dev
npm run dev

# Production
npm run build
```

---

## Configuration PWA (Share Target)

Le Share Target permet à WaziScope d'apparaître dans la liste "Partager" de votre téléphone.

### Manifest (`public/manifest.json`)

Le fichier `manifest.json` est déjà configuré avec :

```json
"share_target": {
  "action": "/share",
  "method": "GET",
  "params": {
    "title": "title",
    "text": "text",
    "url": "url"
  }
}
```

### Pour que le Share Target fonctionne

1. **Le site doit être servi en HTTPS** (obligatoire pour les PWA)
2. **L'utilisateur doit installer l'app** depuis le navigateur Chrome/Edge/Safari
3. Sur Android : "Ajouter à l'écran d'accueil" ou banner automatique
4. Sur iOS Safari : "Partager" → "Sur l'écran d'accueil"

Une fois installée, WaziScope apparaît dans la liste "Partager" de toutes les apps.

---

## Routes API

```
GET  /api/v1/health           — État du service Laravel + FastAPI
GET  /api/v1/platforms        — Plateformes supportées
GET  /api/v1/detect?url=...   — Détecter la plateforme sans extraire
POST /api/v1/extract          — Extraire une vidéo { url: "..." }
POST /api/v1/extract/batch    — Extraire plusieurs vidéos { urls: [...] }
GET  /api/v1/download         — Proxy de téléchargement ?url=...&filename=...&platform=...
```

### Exemple de réponse `/api/v1/extract`

```json
{
  "success": true,
  "duration_ms": 1240,
  "data": {
    "original_url": "https://www.tiktok.com/@user/video/123",
    "title": "Titre de la vidéo",
    "author": "username",
    "thumbnail": "https://cdn.tiktok.com/...",
    "duration": 30.0,
    "view_count": 150000,
    "platform": "tiktok",
    "best_url": "https://v19.tiktokcdn.com/...",
    "no_watermark_url": "https://v19.tiktokcdn.com/...",
    "audio_only_url": null,
    "proxy_download_url": "https://votre-domaine.com/api/v1/download?url=...&platform=tiktok",
    "formats": [
      {
        "format_id": "0",
        "ext": "mp4",
        "quality": "720p",
        "height": 720,
        "no_watermark": true,
        "proxy_url": "https://votre-domaine.com/api/v1/download?..."
      }
    ]
  }
}
```

---

## Résolution de bugs connus

### Bug : le fichier téléchargé s'appelle `video.mp4.json`

**Cause** : Le proxy de téléchargement Laravel renvoyait une réponse JSON d'erreur (403 domaine non autorisé ou headers manquants). Le navigateur voyait `Content-Type: application/json` mais le nom était `.mp4` → OS ajoutait `.json`.

**Fix v2.1** : Le proxy utilise maintenant **cURL** avec les headers spécifiques à chaque plateforme (User-Agent Android pour TikTok, Referer correct, etc.). Un check HEAD préalable détecte les URLs expirées et retourne une erreur explicite avant de streamer.

Si le problème persiste, l'URL CDN a **expiré** (TikTok expire ses CDN URLs en quelques minutes). Solution : ré-extraire la vidéo.

### Bug : Pinterest ne fonctionne pas

**Cause** : L'API Pinterest bloque les requêtes yt-dlp depuis 2024.

**Fix v2.1** : Fallback scraper HTML intégré dans le service Python. Il parse `__PWS_DATA__` et `__redux_data__` directement depuis le HTML de la page Pinterest. Fonctionne pour les vidéos publiques. Les vidéos de boards privés ou les pins d'utilisateurs avec compte privé restent inaccessibles.

**Note `pin.it`** : Les URLs courtes `pin.it/xxx` sont d'abord résolues vers `pinterest.com/pin/xxx` avant extraction.

### TikTok : vidéo avec watermark malgré tout

yt-dlp TikTok est sensible aux changements de l'API. Mettre à jour régulièrement :
```bash
pip install -U yt-dlp
```

---

## Mise à jour yt-dlp

yt-dlp doit être mis à jour **fréquemment** (les sites changent leurs APIs régulièrement).

```bash
# Manuel
pip install -U yt-dlp

# Automatique (cron job)
# crontab -e
0 3 * * 1 pip install -U yt-dlp  # Chaque lundi à 3h
```

---

## Déploiement production

### Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name votre-domaine.com;

    root /var/www/waziscope/public;
    index index.php;

    # Laravel
    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php/php8.2-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
        include fastcgi_params;
    }

    # Proxy vers FastAPI (optionnel, si accès direct)
    location /extractor/ {
        proxy_pass http://127.0.0.1:8032/;
        proxy_set_header Host $host;
    }

    # SW doit être servi depuis la racine
    location /sw.js {
        add_header Cache-Control "no-cache";
        try_files $uri /index.php?$query_string;
    }
}
```

### Variables d'environnement production

```env
APP_ENV=production
APP_DEBUG=false
APP_URL=https://votre-domaine.com

CACHE_DRIVER=redis   # Ou file si Redis indisponible
SESSION_DRIVER=redis

WAZISCOPE_EXTRACTOR_URL=http://127.0.0.1:8032
```

---

## Structure du projet

```
waziscope_wpa/
├── extractor/                  # Service Python FastAPI
│   ├── main.py                 # Serveur FastAPI + extraction
│   └── requirements.txt
├── app/
│   └── Http/
│       └── Controllers/
│           └── VideoController.php
├── routes/
│   ├── api.php
│   └── web.php
├── resources/
│   ├── js/
│   │   ├── app.js
│   │   └── views/
│   │       ├── HomeView.vue
│   │       ├── HistoryView.vue
│   │       └── ShareView.vue
│   ├── views/
│   │   └── app.blade.php
│   └── App.vue
└── public/
    ├── manifest.json
    ├── sw.js
    └── offline.html
```

---

## Contribuer

Les PR sont bienvenues. Points d'amélioration identifiés :

- [ ] Authentification utilisateur (quota de téléchargement)
- [ ] Support Instagram Stories / Reels avec cookies
- [ ] Téléchargement en arrière-plan (Background Sync API)
- [ ] Raccourcisseur d'URL intégré pour partage
- [ ] Support Snapchat Spotlight
- [ ] Monitoring des URLs expirées TikTok

---

## Licence

MIT — voir [LICENSE](LICENSE)

---

## Avertissement

WaziScope est destiné au **téléchargement de contenu dont vous êtes l'auteur** ou pour lequel vous disposez des droits nécessaires. L'utilisation de cet outil pour télécharger du contenu protégé par des droits d'auteur sans autorisation est de la responsabilité de l'utilisateur. Les auteurs de ce projet déclinent toute responsabilité quant à l'usage qui en est fait.

---

*Développé par [Roger Gnanih](https://roger.nealix.org) · Nealix· Bénin*