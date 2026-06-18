#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LARAVEL="$ROOT/laravel"
EXTRACTOR="$ROOT/extractor"
LOG="$ROOT/deploy.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== WaziScope Deploy START ==="

# ── 1. Git pull ───────────────────────────────────────────────────────────────
log "Git: pull origin main..."
git -C "$ROOT" reset --hard HEAD
git -C "$ROOT" pull origin main
log "Git: OK ($(git -C "$ROOT" rev-parse --short HEAD))"

# ── 2. Laravel — PHP deps ──────────────────────────────────────────────────────
log "Composer: install..."
composer install \
  --working-dir="$LARAVEL" \
  --no-interaction \
  --no-dev \
  --optimize-autoloader \
  --quiet
log "Composer: OK"

# ── 3. Laravel — frontend ─────────────────────────────────────────────────────
log "NPM: build..."
cd "$LARAVEL"
npm ci --silent
npm run build --silent
log "NPM: OK"

# ── 4. Laravel — artisan ──────────────────────────────────────────────────────
log "Artisan: migrate + cache..."
php "$LARAVEL/artisan" migrate --force --quiet
php "$LARAVEL/artisan" config:cache --quiet
php "$LARAVEL/artisan" route:cache  --quiet
php "$LARAVEL/artisan" view:cache   --quiet
php "$LARAVEL/artisan" event:cache  --quiet
log "Artisan: OK"

# ── 5. Python extractor — pip sync ────────────────────────────────────────────
log "Python: pip install..."
if [ ! -f "$EXTRACTOR/venv/bin/activate" ]; then
  log "Python: création venv..."
  python3 -m venv "$EXTRACTOR/venv"
fi
"$EXTRACTOR/venv/bin/pip" install -q --upgrade pip
"$EXTRACTOR/venv/bin/pip" install -q -r "$EXTRACTOR/requirements.txt"
log "Python: OK"

# ── 6. Supervisor — restart extractor ─────────────────────────────────────────
log "Supervisor: restart extractor..."
if command -v supervisorctl &>/dev/null; then
  supervisorctl restart waziscope-extractor || supervisorctl start waziscope-extractor
  log "Supervisor: OK"
else
  log "Supervisor: non trouvé — extractor non redémarré"
fi

# ── 7. Optionnel — reload PHP-FPM ─────────────────────────────────────────────
if command -v php-fpm8.3 &>/dev/null; then
  sudo service php8.3-fpm reload 2>/dev/null && log "PHP-FPM: reloaded" || true
elif command -v php-fpm &>/dev/null; then
  sudo service php-fpm reload 2>/dev/null && log "PHP-FPM: reloaded" || true
fi

log "=== WaziScope Deploy OK ==="
echo ""
echo "  Branch : $(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
echo "  Commit : $(git -C "$ROOT" log -1 --pretty='%h — %s')"
echo "  Durée  : ${SECONDS}s"
