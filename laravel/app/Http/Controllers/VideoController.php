<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Cache;
use Symfony\Component\HttpFoundation\StreamedResponse;

class VideoController extends Controller
{
    private string $extractorUrl;

    private const CACHE_TTL      = 600;  // 10 min
    private const EXTRACT_TIMEOUT = 60;
    private const FAST_TIMEOUT    = 5;

    /**
     * Domaines autorisés pour le proxy.
     * Clé = pattern de domaine, valeur = plateforme associée.
     */
    private const ALLOWED_PROXY_DOMAINS = [
        // TikTok — tous les CDN possibles
        'tiktokcdn.com', 'tiktokv.com', 'tiktokcdn-us.com',
        'tiktokcdn-eu.com', 'byteoversea.com', 'tiktok.com',
        'musical.ly', 'p16-sign.tiktokcdn-us.com',
        // Pinterest
        'pinimg.com', 'pinterest.com',
        // Facebook / Meta
        'fbcdn.net', 'facebook.com', 'fbsbx.com',
        // Instagram
        'cdninstagram.com', 'instagram.com',
        // YouTube (googlevideo sert les fichiers réels)
        'googlevideo.com', 'youtube.com', 'ytimg.com',
        // LinkedIn
        'licdn.com', 'linkedin.com',
        // Twitter / X
        'twimg.com', 'twitter.com', 'x.com',
        // CDN génériques
        'akamaihd.net', 'cloudfront.net', 'akamai.net',
    ];

    /**
     * Headers de téléchargement par plateforme.
     * Synchronisés avec Python DOWNLOAD_HEADERS.
     */
    private const PLATFORM_DOWNLOAD_HEADERS = [
        'tiktok' => [
            'User-Agent' => 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36',
            'Referer'    => 'https://www.tiktok.com/',
            'Accept'     => 'video/mp4,video/*;q=0.9,*/*;q=0.8',
            'Accept-Language' => 'fr-FR,fr;q=0.9,en;q=0.7',
        ],
        'youtube' => [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer'    => 'https://www.youtube.com/',
            'Accept'     => 'video/mp4,video/*;q=0.9,*/*;q=0.8',
        ],
        'pinterest' => [
            'User-Agent' => 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
            'Referer'    => 'https://www.pinterest.com/',
            'Accept'     => 'video/mp4,video/*;q=0.9,*/*;q=0.8',
        ],
        'facebook' => [
            'User-Agent' => 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36',
            'Referer'    => 'https://www.facebook.com/',
            'Accept'     => 'video/mp4,video/*;q=0.9,*/*;q=0.8',
        ],
        'instagram' => [
            'User-Agent' => 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36',
            'Referer'    => 'https://www.instagram.com/',
            'Accept'     => 'video/mp4,video/*;q=0.9,*/*;q=0.8',
        ],
        'linkedin' => [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer'    => 'https://www.linkedin.com/',
            'Accept'     => 'video/mp4,video/*;q=0.9,*/*;q=0.8',
        ],
        'twitter' => [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer'    => 'https://twitter.com/',
            'Accept'     => 'video/mp4,video/*;q=0.9,*/*;q=0.8',
        ],
    ];

    public function __construct()
    {
        $this->extractorUrl = config('services.waziscope.extractor_url', 'http://localhost:8032');
    }

    // ─── Health ────────────────────────────────────────────────────────────────

    public function health(): JsonResponse
    {
        try {
            $python = Http::timeout(self::FAST_TIMEOUT)
                ->get("{$this->extractorUrl}/health")->json();
        } catch (\Exception) {
            $python = ['status' => 'unreachable'];
        }
        return response()->json(['status' => 'ok', 'service' => 'waziscope-laravel', 'extractor' => $python]);
    }

    // ─── Plateformes ───────────────────────────────────────────────────────────

    public function platforms(): JsonResponse
    {
        $fallback = ['platforms' => [
            ['id' => 'tiktok',    'name' => 'TikTok',    'no_watermark' => true],
            ['id' => 'youtube',   'name' => 'YouTube',   'no_watermark' => false],
            ['id' => 'pinterest', 'name' => 'Pinterest', 'no_watermark' => false],
            ['id' => 'facebook',  'name' => 'Facebook',  'no_watermark' => false],
            ['id' => 'instagram', 'name' => 'Instagram', 'no_watermark' => false],
            ['id' => 'linkedin',  'name' => 'LinkedIn',  'no_watermark' => false],
            ['id' => 'twitter',   'name' => 'Twitter/X', 'no_watermark' => false],
        ]];

        try {
            $res = Http::timeout(self::FAST_TIMEOUT)->get("{$this->extractorUrl}/platforms");
            return response()->json($res->successful() ? $res->json() : $fallback);
        } catch (\Exception) {
            return response()->json($fallback);
        }
    }

    // ─── Detect ────────────────────────────────────────────────────────────────

    public function detect(Request $request): JsonResponse
    {
        $request->validate(['url' => ['required', 'url', 'max:2048']]);
        try {
            $res = Http::timeout(self::FAST_TIMEOUT)
                ->get("{$this->extractorUrl}/detect", ['url' => $request->input('url')]);
            return response()->json($res->successful() ? $res->json() : ['platform' => 'unknown', 'supported' => false]);
        } catch (\Exception) {
            return response()->json(['platform' => 'unknown', 'supported' => false]);
        }
    }

    // ─── Extract ───────────────────────────────────────────────────────────────

    public function extract(Request $request): JsonResponse
    {
        $request->validate(['url' => ['required', 'url', 'max:2048']]);
        $url      = trim($request->input('url'));
        $cacheKey = 'wzs_' . md5($url);

        try {
            $data = Cache::remember($cacheKey, self::CACHE_TTL, function () use ($url) {
                $res = Http::timeout(self::EXTRACT_TIMEOUT)
                    ->get("{$this->extractorUrl}/extract", ['url' => $url]);

                if ($res->serverError()) {
                    throw new \Exception("Extractor error {$res->status()}");
                }
                return $res->json();
            });

            if (!($data['success'] ?? false)) {
                Cache::forget($cacheKey);
                return response()->json([
                    'success' => false,
                    'message' => $data['error'] ?? 'Extraction échouée',
                ], 422);
            }

            return response()->json([
                'success'     => true,
                'data'        => $this->normalizeVideoData($data['data']),
                'duration_ms' => $data['duration_ms'] ?? null,
            ]);

        } catch (\Exception $e) {
            Cache::forget($cacheKey);
            Log::error('WaziScope extract', ['url' => $url, 'error' => $e->getMessage()]);
            return response()->json(['success' => false, 'message' => 'Impossible d\'extraire cette vidéo.'], 500);
        }
    }

    // ─── Extract batch ─────────────────────────────────────────────────────────

    public function extractBatch(Request $request): JsonResponse
    {
        $request->validate([
            'urls'   => ['required', 'array', 'min:1', 'max:10'],
            'urls.*' => ['required', 'url', 'max:2048'],
        ]);

        try {
            $res  = Http::timeout(self::EXTRACT_TIMEOUT * 2)
                ->post("{$this->extractorUrl}/extract/batch", ['urls' => $request->input('urls')]);

            $data = $res->json();
            if (isset($data['results'])) {
                $data['results'] = array_map(function ($r) {
                    if (($r['success'] ?? false) && isset($r['data'])) {
                        $r['data'] = $this->normalizeVideoData($r['data']);
                    }
                    return $r;
                }, $data['results']);
            }
            return response()->json($data);

        } catch (\Exception $e) {
            Log::error('WaziScope batch', ['error' => $e->getMessage()]);
            return response()->json(['success' => false, 'message' => 'Erreur batch'], 500);
        }
    }

    // ─── Download proxy ────────────────────────────────────────────────────────
    //
    // FIX .mp4.json : le bug venait de fopen() PHP qui échouait sans les bons
    // headers TikTok → Laravel renvoyait une réponse JSON d'erreur → le browser
    // voyait Content-Type application/json mais le filename était .mp4
    // → OS ajoutait .json → fichier .mp4.json
    //
    // Solution : utiliser cURL avec les headers corrects par plateforme.
    // cURL est bien plus fiable que fopen() pour les CDN avec hotlink protection.

    public function download(Request $request): StreamedResponse|JsonResponse
    {
        $request->validate([
            'url'      => ['required', 'url'],
            'filename' => ['nullable', 'string', 'max:255'],
            'platform' => ['nullable', 'string', 'max:30'],
        ]);

        $videoUrl = $request->input('url');
        $platform = $request->input('platform', $this->detectPlatformFromUrl($videoUrl));
        $filename = $this->sanitizeFilename(
            $request->input('filename', 'video_' . time() . '.mp4')
        );

        // ── Vérification domaine ────────────────────────────────────────────
        if (!$this->isAllowedDomain($videoUrl)) {
            Log::warning('WaziScope download: domaine non autorisé', ['url' => $videoUrl]);
            return response()->json(['success' => false, 'message' => 'Source non autorisée'], 403);
        }

        // ── Vérifier que cURL est disponible ───────────────────────────────
        if (!function_exists('curl_init')) {
            // Fallback fopen si cURL absent (rare)
            return $this->downloadWithFopen($videoUrl, $filename, $platform);
        }

        return $this->downloadWithCurl($videoUrl, $filename, $platform);
    }

    /**
     * Download via cURL — plus fiable, supporte tous les headers custom.
     * Corrige le bug .mp4.json.
     */
    private function downloadWithCurl(string $videoUrl, string $filename, string $platform): StreamedResponse|JsonResponse
    {
        // Déterminer le Content-Type
        $ext         = strtolower(pathinfo(parse_url($videoUrl, PHP_URL_PATH) ?? '', PATHINFO_EXTENSION));
        $contentType = match ($ext) {
            'webm'  => 'video/webm',
            'm4a'   => 'audio/mp4',
            'mp3'   => 'audio/mpeg',
            default => 'video/mp4',
        };

        // Headers spécifiques à la plateforme
        $headers = self::PLATFORM_DOWNLOAD_HEADERS[$platform] ?? self::PLATFORM_DOWNLOAD_HEADERS['tiktok'];

        // Vérifier d'abord que l'URL est accessible (HEAD request)
        $checkResult = $this->curlHead($videoUrl, $headers);
        if ($checkResult['http_code'] >= 400 && $checkResult['http_code'] !== 0) {
            Log::warning('WaziScope download: URL inaccessible', [
                'url'  => substr($videoUrl, 0, 100),
                'code' => $checkResult['http_code'],
            ]);
            return response()->json([
                'success' => false,
                'message' => "L'URL vidéo a expiré ou n'est plus accessible (code {$checkResult['http_code']}). Veuillez extraire à nouveau.",
            ], 410);
        }

        return response()->streamDownload(
            function () use ($videoUrl, $headers) {
                $ch = curl_init();
                curl_setopt_array($ch, [
                    CURLOPT_URL            => $videoUrl,
                    CURLOPT_FOLLOWLOCATION => true,
                    CURLOPT_MAXREDIRS      => 5,
                    CURLOPT_TIMEOUT        => 120,
                    CURLOPT_CONNECTTIMEOUT => 15,
                    CURLOPT_HTTPHEADER     => $this->formatCurlHeaders($headers),
                    CURLOPT_SSL_VERIFYPEER => true,
                    CURLOPT_ENCODING       => '',  // Accepter toutes les encodages
                    CURLOPT_BUFFERSIZE     => 65536, // 64KB chunks
                    // Écrire directement dans le buffer de sortie
                    CURLOPT_WRITEFUNCTION  => function ($ch, $data) {
                        echo $data;
                        if (ob_get_level() > 0) ob_flush();
                        flush();
                        return strlen($data);
                    },
                    // Pas de header dans la sortie
                    CURLOPT_HEADER         => false,
                    CURLOPT_RETURNTRANSFER => false,
                ]);

                curl_exec($ch);

                $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                $error    = curl_error($ch);
                curl_close($ch);

                if ($error) {
                    Log::error('WaziScope cURL stream error', ['error' => $error]);
                }
            },
            $filename,
            [
                'Content-Type'        => $contentType,
                'Content-Disposition' => 'attachment; filename="' . $filename . '"',
                'Cache-Control'       => 'no-cache, no-store, must-revalidate',
                'X-Accel-Buffering'   => 'no',
                'Transfer-Encoding'   => 'chunked',
            ]
        );
    }

    /**
     * Fallback avec fopen() si cURL absent.
     */
    private function downloadWithFopen(string $videoUrl, string $filename, string $platform): StreamedResponse
    {
        $headers = self::PLATFORM_DOWNLOAD_HEADERS[$platform] ?? [];
        $httpHeaders = array_map(
            fn($k, $v) => "$k: $v",
            array_keys($headers),
            array_values($headers)
        );
        $httpHeaders[] = 'Range: bytes=0-';

        return response()->streamDownload(function () use ($videoUrl, $httpHeaders) {
            $context = stream_context_create([
                'http' => [
                    'method'          => 'GET',
                    'follow_location' => true,
                    'max_redirects'   => 5,
                    'timeout'         => 90,
                    'header'          => implode("\r\n", $httpHeaders),
                ],
                'ssl' => ['verify_peer' => true, 'verify_peer_name' => true],
            ]);

            $stream = @fopen($videoUrl, 'r', false, $context);
            if ($stream) {
                try {
                    while (!feof($stream)) {
                        $chunk = fread($stream, 65536);
                        if ($chunk === false) break;
                        echo $chunk;
                        if (ob_get_level() > 0) ob_flush();
                        flush();
                    }
                } finally {
                    fclose($stream);
                }
            }
        }, $filename, [
            'Content-Type'      => 'video/mp4',
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
            'Cache-Control'     => 'no-cache',
            'X-Accel-Buffering' => 'no',
        ]);
    }

    // ─── Private helpers ────────────────────────────────────────────────────────

    /**
     * Fait une requête HEAD cURL pour vérifier l'accessibilité de l'URL.
     */
    private function curlHead(string $url, array $headers): array
    {
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL            => $url,
            CURLOPT_NOBODY         => true,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS      => 3,
            CURLOPT_TIMEOUT        => 10,
            CURLOPT_HTTPHEADER     => $this->formatCurlHeaders($headers),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_SSL_VERIFYPEER => true,
        ]);
        curl_exec($ch);
        $result = [
            'http_code' => (int) curl_getinfo($ch, CURLINFO_HTTP_CODE),
            'error'     => curl_error($ch),
        ];
        curl_close($ch);
        return $result;
    }

    /**
     * Convertit un array associatif d'headers en array cURL.
     */
    private function formatCurlHeaders(array $headers): array
    {
        return array_map(
            fn($k, $v) => "$k: $v",
            array_keys($headers),
            array_values($headers)
        );
    }

    /**
     * Détecte la plateforme depuis l'URL pour choisir les bons headers.
     */
    private function detectPlatformFromUrl(string $url): string
    {
        $url = strtolower($url);
        if (str_contains($url, 'tiktok'))              return 'tiktok';
        if (str_contains($url, 'youtu'))               return 'youtube';
        if (str_contains($url, 'pinterest') || str_contains($url, 'pinimg')) return 'pinterest';
        if (str_contains($url, 'facebook') || str_contains($url, 'fbcdn'))   return 'facebook';
        if (str_contains($url, 'instagram') || str_contains($url, 'cdninstagram')) return 'instagram';
        if (str_contains($url, 'linkedin') || str_contains($url, 'licdn'))   return 'linkedin';
        if (str_contains($url, 'twitter') || str_contains($url, 'twimg'))    return 'twitter';
        return 'tiktok'; // défaut le plus strict
    }

    /**
     * Normalise les données VideoInfo depuis Python v2.
     */
    private function normalizeVideoData(array $data): array
    {
        $platform = $data['platform'] ?? 'unknown';
        $bestUrl  = $data['no_watermark_url'] ?? $data['best_url'] ?? '';

        return [
            'original_url'       => $data['original_url']    ?? '',
            'title'              => $data['title']            ?? 'Vidéo sans titre',
            'description'        => $data['description']      ?? null,
            'author'             => $data['author']           ?? null,
            'thumbnail'          => $data['thumbnail']        ?? null,
            'duration'           => $data['duration']         ?? null,
            'view_count'         => $data['view_count']       ?? null,
            'like_count'         => $data['like_count']       ?? null,
            'platform'           => $platform,
            'best_url'           => $data['best_url']         ?? null,
            'no_watermark_url'   => $data['no_watermark_url'] ?? null,
            'audio_only_url'     => $data['audio_only_url']   ?? null,
            'required_headers'   => $data['required_headers'] ?? [],
            'formats'            => $this->normalizeFormats($data['formats'] ?? [], $platform),
            // URL proxy pré-calculée avec platform param pour les bons headers
            'proxy_download_url' => $this->buildProxyUrl($bestUrl, $data['title'] ?? 'video', $platform),
        ];
    }

    private function normalizeFormats(array $formats, string $platform): array
    {
        return array_map(fn($fmt) => [
            'format_id'    => $fmt['format_id']    ?? 'unknown',
            'ext'          => $fmt['ext']           ?? 'mp4',
            'quality'      => $fmt['quality']       ?? '?',
            'url'          => $fmt['url']           ?? '',
            'filesize'     => $fmt['filesize']      ?? null,
            'width'        => $fmt['width']         ?? null,
            'height'       => $fmt['height']        ?? null,
            'fps'          => $fmt['fps']           ?? null,
            'vcodec'       => $fmt['vcodec']        ?? null,
            'acodec'       => $fmt['acodec']        ?? null,
            'no_watermark' => $fmt['no_watermark']  ?? false,
            'proxy_url'    => $this->buildProxyUrl($fmt['url'] ?? '', '', $platform),
        ], $formats);
    }

    private function buildProxyUrl(string $videoUrl, string $title, string $platform = ''): string
    {
        if (!$videoUrl) return '';
        return url('/api/v1/download') . '?' . http_build_query([
            'url'      => $videoUrl,
            'filename' => $this->sanitizeFilename($title ?: 'video') . '.mp4',
            'platform' => $platform,
        ]);
    }

    private function isAllowedDomain(string $url): bool
    {
        $host = strtolower(parse_url($url, PHP_URL_HOST) ?? '');
        if (!$host) return false;
        foreach (self::ALLOWED_PROXY_DOMAINS as $domain) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) return true;
        }
        return false;
    }

    private function sanitizeFilename(string $name): string
    {
        $name = preg_replace('/[^\w\-. ]/u', '_', $name);
        $name = preg_replace('/\s+/', '_', trim($name ?? ''));
        return substr($name ?: 'video', 0, 100);
    }
}
