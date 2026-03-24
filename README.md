# WaziScope PWA

> Télécharge des vidéos TikTok (sans watermark), Pinterest et Facebook directement depuis le bouton **Partager** de n'importe quelle app mobile.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MOBILE (Android / iOS)                    │
│                                                              │
│  TikTok / Pinterest / Facebook                               │
│         │  [Bouton Partager]                                 │
│         ▼                                                    │
│  Share Sheet natif  ──►  WaziScope PWA apparaît             │
│         │                                                    │
│         ▼  (?shared=URL)                                     │
└─────────────────────────────────────────────────────────────┘
                          │
           ┌──────────────▼──────────────┐
           │   Laravel (Vue.js PWA)       │  :80
           │   - Web Share Target API     │
           │   - Proxy de téléchargement  │
           │   POST /api/v1/extract       │
           └──────────────┬──────────────┘
                          │
           ┌──────────────▼──────────────┐
           │   FastAPI (Python)           │  :8032
           │   - yt-dlp                   │
           │   - Extraction URL vidéo     │
           │   - TikTok no-watermark      │
           └─────────────────────────────┘
```

---

## Installation

### 1. Cloner et démarrer

```bash
git clone https://github.com/ton-user/waziscope.git
cd waziscope

# Lancer avec Docker
docker-compose up -d
```

### 2. Sans Docker (développement)

**FastAPI service :**
```bash
cd extractor
pip install -r requirements.txt
uvicorn main:app --reload --port 8032
```

**Laravel + Vue.js :**
```bash
cd laravel
composer install
cp .env.example .env
php artisan key:generate

# Configurer l'URL du service FastAPI
echo "VIDEODOWN_EXTRACTOR_URL=http://localhost:8032" >> .env

npm install
npm run dev

php artisan serve
```

---

## Config Laravel (.env)

```env
APP_NAME=WaziScope
APP_ENV=production
APP_URL=https://ton-domaine.com

# URL du service FastAPI extractor
VIDEODOWN_EXTRACTOR_URL=http://localhost:8032
```

---

## Config services (config/services.php)

```php
'waziscope' => [
    'extractor_url' => env('VIDEODOWN_EXTRACTOR_URL', 'http://localhost:8032'),
],
```

---

## Routes Laravel (web.php)

Ajouter une route catch-all pour Vue Router :

```php
// routes/web.php
Route::get('/{any}', function () {
    return view('app');
})->where('any', '.*');
```

---

## Web Share Target API

Le `manifest.json` déclare le Share Target :

```json
"share_target": {
  "action": "/share",
  "method": "GET",
  "params": {
    "url": "url",
    "text": "text"
  }
}
```

**Comportement :**
1. L'utilisateur installe la PWA (bouton "Ajouter à l'écran d'accueil")
2. Dans TikTok → appui sur "Partager" → WaziScope apparaît
3. Le Service Worker intercepte `/share?url=...`
4. Redirige vers `/?shared=URL`
5. Vue.js détecte l'URL et lance l'extraction automatiquement

---

## Plateformes supportées

| Plateforme | Sans watermark | Status |
|------------|---------------|--------|
| TikTok     | ✅ Oui        | ✅ Actif |
| Pinterest  | ❌ Non        | ✅ Actif |
| Facebook   | ❌ Non        | ✅ Actif |

---

## API FastAPI

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Health check |
| `/extract?url=` | GET | Extraire une vidéo |
| `/platforms` | GET | Plateformes supportées |

---

## Compatibilité PWA Share Target

| Plateforme | Support |
|-----------|---------|
| Android Chrome | ✅ Complet |
| Android Edge | ✅ Complet |
| iOS Safari 16.4+ | ⚠️ Partiel (Share Target limité) |
| Desktop Chrome | ✅ (via URL manuelle) |

> **Note iOS :** Sur iOS, le Web Share Target API est encore limité. L'utilisateur peut copier l'URL et la coller manuellement dans WaziScope.

---

## Structure des fichiers

```
waziscope/
├── extractor/              # Service Python FastAPI
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── laravel/                # App Laravel + Vue.js PWA
│   ├── app/Http/Controllers/VideoController.php
│   ├── routes/api.php
│   ├── public/
│   │   ├── manifest.json   # PWA manifest (Share Target)
│   │   └── sw.js           # Service Worker
│   └── resources/js/
│       ├── app.js          # Point d'entrée Vue
│       ├── App.vue         # Layout + Install banner
│       └── views/
│           ├── HomeView.vue    # Extracteur principal
│           └── HistoryView.vue # Historique
├── docker-compose.yml
└── README.md
```