FROM php:8.3-fpm-alpine

# ── Extensions système ────────────────────────────────────────────────────────
RUN apk add --no-cache \
    curl \
    zip \
    unzip \
    git \
    libpng-dev \
    libjpeg-turbo-dev \
    libwebp-dev \
    freetype-dev \
    oniguruma-dev \
    libxml2-dev \
    libzip-dev \
    icu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j$(nproc) \
        bcmath \
        ctype \
        fileinfo \
        gd \
        intl \
        mbstring \
        opcache \
        pcntl \
        pdo \
        pdo_mysql \
        tokenizer \
        xml \
        zip \
    && apk del --no-cache libpng-dev libjpeg-turbo-dev libwebp-dev freetype-dev

# ── Opcache production ────────────────────────────────────────────────────────
RUN echo "opcache.enable=1" >> /usr/local/etc/php/conf.d/opcache.ini \
 && echo "opcache.memory_consumption=128" >> /usr/local/etc/php/conf.d/opcache.ini \
 && echo "opcache.max_accelerated_files=10000" >> /usr/local/etc/php/conf.d/opcache.ini \
 && echo "opcache.validate_timestamps=0" >> /usr/local/etc/php/conf.d/opcache.ini \
 && echo "opcache.revalidate_freq=0" >> /usr/local/etc/php/conf.d/opcache.ini

# ── Composer ─────────────────────────────────────────────────────────────────
COPY --from=composer:2.8 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

# ── Dépendances Composer (couche cacheable) ───────────────────────────────────
COPY composer.json composer.lock ./
RUN composer install \
    --no-dev \
    --no-scripts \
    --no-autoloader \
    --prefer-dist \
    --no-interaction \
    --no-progress

# ── Code source ───────────────────────────────────────────────────────────────
COPY . .

# ── Autoloader optimisé ───────────────────────────────────────────────────────
# post-autoload-dump (artisan package:discover) nécessite APP_KEY — on le skip
# au build et on le lance au démarrage du container via CMD ou entrypoint.
RUN composer dump-autoload --optimize --no-dev

# ── Storage / cache writeable par www-data ───────────────────────────────────
RUN chown -R www-data:www-data storage bootstrap/cache \
 && chmod -R 775 storage bootstrap/cache

# PHP-FPM écoute sur le port 9000 (utilisé par nginx via fastcgi_pass app:9000)
EXPOSE 9000

# Entrypoint : package:discover + caches Laravel au démarrage (besoin de .env monté)
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["php-fpm"]
