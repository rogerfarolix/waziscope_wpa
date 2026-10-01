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

# Vérifier les changements non committés avant reset --hard
DIRTY="$(git -C "$ROOT" status --porcelain 2>/dev/null)"
if [ -n "$DIRTY" ]; then
  log "AVERTISSEMENT: des changements locaux non committés vont être perdus :"
  git -C "$ROOT" status --short | tee -a "$LOG"
  log "Stash automatique..."
  git -C "$ROOT" stash push -u -m "deploy-stash-$(date +%Y%m%d-%H%M%S)" || true
fi

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
REQ_HASH_FILE="$EXTRACTOR/venv/.req_hash"
REQ_HASH="$(md5sum "$EXTRACTOR/requirements.txt" 2>/dev/null | cut -d' ' -f1)"
SAVED_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || echo '')"

if [ "$REQ_HASH" != "$SAVED_HASH" ]; then
  "$EXTRACTOR/venv/bin/pip" install -q --upgrade pip
  "$EXTRACTOR/venv/bin/pip" install -q -r "$EXTRACTOR/requirements.txt"
  echo "$REQ_HASH" > "$REQ_HASH_FILE"
  log "Python: deps mis à jour"
else
  log "Python: deps inchangés (skip)"
fi

# yt-dlp se périme en quelques semaines (YouTube change son API) — toujours upgrader
log "Python: mise à jour yt-dlp..."
"$EXTRACTOR/venv/bin/pip" install -q --upgrade yt-dlp
log "Python: yt-dlp $("$EXTRACTOR/venv/bin/yt-dlp" --version)"
log "Python: OK"

# ── 6. Supervisor — restart extractor ─────────────────────────────────────────
log "Supervisor: restart extractor..."
if command -v supervisorctl &>/dev/null; then
  sudo supervisorctl restart waziscope-extractor 2>/dev/null \
    || sudo supervisorctl start waziscope-extractor 2>/dev/null \
    || log "Supervisor: permission manquante — voir /etc/sudoers.d/waziscope-deploy"
  log "Supervisor: OK"
else
  log "Supervisor: non trouvé — extractor non redémarré"
fi

# ── 7. Optionnel — reload PHP-FPM ─────────────────────────────────────────────
if sudo service php8.3-fpm status &>/dev/null; then
  sudo service php8.3-fpm reload 2>/dev/null && log "PHP-FPM 8.3: reloaded" || true
elif sudo service php-fpm status &>/dev/null; then
  sudo service php-fpm reload 2>/dev/null && log "PHP-FPM: reloaded" || true
fi

log "=== WaziScope Deploy OK ==="
echo ""
echo "  Branch : $(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
echo "  Commit : $(git -C "$ROOT" log -1 --pretty='%h — %s')"
echo "  Durée  : ${SECONDS}s"
