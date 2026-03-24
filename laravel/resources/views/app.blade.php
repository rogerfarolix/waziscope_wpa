<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />

    <title>WaziScope — Télécharge TikTok, YouTube, Pinterest sans watermark</title>
    <meta name="description" content="Télécharge des vidéos TikTok sans watermark, YouTube, Pinterest, Facebook, Instagram depuis les apps via le bouton Partager." />

    <!-- ── PWA ──────────────────────────────────────────────────────────── -->
    <link rel="manifest" href="/manifest.json" />
    <meta name="theme-color" content="#080b0f" />
    <meta name="color-scheme" content="dark" />

    <!-- Mobile standalone -->
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="apple-mobile-web-app-title" content="WaziScope" />

    <!-- Apple icons -->
    <link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-192.png" />
    <link rel="icon" type="image/png" sizes="32x32" href="/icons/icon-96.png" />

    <!-- ── OG / Social ──────────────────────────────────────────────────── -->
    <meta property="og:type"        content="website" />
    <meta property="og:title"       content="WaziScope — Téléchargeur vidéo" />
    <meta property="og:description" content="TikTok sans watermark · YouTube · Pinterest · Facebook · Instagram" />
    <meta property="og:image"       content="/og-image.png" />
    <meta name="twitter:card"       content="summary_large_image" />

    <!-- ── Fonts (Bricolage Grotesque + Outfit + Fira Code) ─────────────── -->
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
        href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600;12..96,700;12..96,800&family=Outfit:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap"
        rel="stylesheet"
    />

    <!-- ── Vite ─────────────────────────────────────────────────────────── -->
    @vite(['resources/js/app.js'])
</head>
<body>
    <div id="app"></div>
</body>
</html>
