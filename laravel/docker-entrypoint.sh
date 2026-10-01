#!/bin/sh
set -e

# Lancer package:discover + caches Laravel au premier démarrage.
# À ce stade le volume .env est monté par docker-compose.
if [ -f ".env" ]; then
    php artisan package:discover --ansi 2>/dev/null || true
    php artisan config:cache   --quiet 2>/dev/null || true
    php artisan route:cache    --quiet 2>/dev/null || true
    php artisan view:cache     --quiet 2>/dev/null || true
fi

exec "$@"
