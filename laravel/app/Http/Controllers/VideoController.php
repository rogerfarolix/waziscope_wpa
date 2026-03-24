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

    // Durée de cache en secondes
    private const CACHE_TTL = 600; // 10 min

    // Timeout HTTP vers FastAPI
    private const EXTRACT_TIMEOUT = 60; // yt-dlp peut être lent
    private const FAST_TIMEOUT    = 5;

    // Domaines autorisés pour le proxy de téléchargement
    private const ALLOWED_PROXY_DOMAINS = [
        // TikTok CDN
        'tiktokcdn.com', 'tiktokv.com', 'byteoversea.com', 'tiktokcdn-us.com',
        'musical.ly', 'tiktokcdn-eu.com',
        // Pinterest
        'pinimg.com', 'pinterest.com',
        // Facebook / Meta
        'fbcdn.net', 'facebook.com', 'fbsbx.com', 'cdnfacebookcorp.net',
        // Instagram
        'cdninstagram.com', 'instagram.com',
        // YouTube (les CDN Google)
        'googlevideo.com', 'ytimg.com', 'youtube.com',
        // LinkedIn
        'licdn.com', 'linkedin.com',
        // Twitter / X
        'twimg.com', 'twitter.com', 'x.com',
        // Divers CDN vidéo
        'akamaihd.net', 'cloudfront.net',
    ];

    public function __construct()
    {
        $this->extractorUrl = config('services.waziscope.extractor_url', 'http://localhost:8032');
    }

    // ─── Health / Status ────────────────────────────────────────────────────────

    /**
     * GET /api/v1/health
     * Vérifie aussi que le service FastAPI est joignable
     */
    public function health(): JsonResponse
    {
        try {
            $pythonStatus = Http::timeout(self::FAST_TIMEOUT)
                ->get("{$this->extractorUrl}/health")
                ->json();
        } catch (\Exception) {
            $pythonStatus = ['status' => 'unreachable'];
        }

        return response()->json([
            'status'  => 'ok',
            'service' => 'waziscope-laravel',
            'extractor' => $pythonStatus,
        ]);
    }

    // ─── Plateformes ───────────────────────────────────────────────────────────

    /**
     * GET /api/v1/platforms
     */
    public function platforms(): JsonResponse
    {
        // Fallback complet aligné avec Python v2
        $fallback = [
            'platforms' => [
                ['id' => 'tiktok',    'name' => 'TikTok',    'icon' => '🎵', 'no_watermark' => true,  'notes' => 'Sans watermark via API mobile'],
                ['id' => 'youtube',   'name' => 'YouTube',   'icon' => '▶️',  'no_watermark' => false, 'notes' => 'HD jusqu\'à 1080p'],
                ['id' => 'pinterest', 'name' => 'Pinterest', 'icon' => '📌', 'no_watermark' => false, 'notes' => 'MP4 direct'],
                ['id' => 'facebook',  'name' => 'Facebook',  'icon' => '📘', 'no_watermark' => false, 'notes' => 'Vidéos publiques'],
                ['id' => 'instagram', 'name' => 'Instagram', 'icon' => '📸', 'no_watermark' => false, 'notes' => 'Reels & posts publics'],
                ['id' => 'linkedin',  'name' => 'LinkedIn',  'icon' => '💼', 'no_watermark' => false, 'notes' => 'Vidéos natives'],
                ['id' => 'twitter',   'name' => 'Twitter/X', 'icon' => '🐦', 'no_watermark' => false, 'notes' => 'Vidéos tweets'],
            ],
        ];

        try {
            $response = Http::timeout(self::FAST_TIMEOUT)->get("{$this->extractorUrl}/platforms");
            return response()->json($response->successful() ? $response->json() : $fallback);
        } catch (\Exception) {
            return response()->json($fallback);
        }
    }

    // ─── Détection rapide ──────────────────────────────────────────────────────

    /**
     * GET /api/v1/detect?url=...
     * Détecte la plateforme d'une URL sans extraction (rapide, pas de cache)
     */
    public function detect(Request $request): JsonResponse
    {
        $request->validate(['url' => ['required', 'url', 'max:2048']]);
        $url = $request->input('url');

        try {
            $response = Http::timeout(self::FAST_TIMEOUT)
                ->get("{$this->extractorUrl}/detect", ['url' => $url]);

            return response()->json($response->successful()
                ? $response->json()
                : ['url' => $url, 'platform' => 'unknown', 'supported' => false]
            );
        } catch (\Exception $e) {
            return response()->json(['url' => $url, 'platform' => 'unknown', 'supported' => false]);
        }
    }

    // ─── Extraction simple ─────────────────────────────────────────────────────

    /**
     * POST /api/v1/extract
     * Body: { "url": "https://..." }
     *
     * Retourne VideoInfo complet (aligné avec Python v2 VideoInfo schema)
     */
    public function extract(Request $request): JsonResponse
    {
        $request->validate([
            'url' => ['required', 'url', 'max:2048'],
        ]);

        $url      = trim($request->input('url'));
        $cacheKey = 'wzs_extract_' . md5($url);

        try {
            $data = Cache::remember($cacheKey, self::CACHE_TTL, function () use ($url) {
                $response = Http::timeout(self::EXTRACT_TIMEOUT)
                    ->get("{$this->extractorUrl}/extract", ['url' => $url]);

                if ($response->serverError()) {
                    throw new \Exception("Le service d'extraction a retourné une erreur {$response->status()}");
                }

                return $response->json();
            });

            if (! ($data['success'] ?? false)) {
                // On retire du cache si l'extraction a échoué
                Cache::forget($cacheKey);

                return response()->json([
                    'success' => false,
                    'message' => $data['error'] ?? 'Extraction échouée',
                ], 422);
            }

            // Enrichir la réponse avec des champs normalisés
            return response()->json([
                'success'     => true,
                'data'        => $this->normalizeVideoData($data['data']),
                'duration_ms' => $data['duration_ms'] ?? null,
            ]);

        } catch (\Exception $e) {
            Cache::forget($cacheKey);
            Log::error('WaziScope extract error', [
                'url'   => $url,
                'error' => $e->getMessage(),
            ]);

            return response()->json([
                'success' => false,
                'message' => 'Impossible d\'extraire cette vidéo. Vérifiez l\'URL ou réessayez.',
            ], 500);
        }
    }

    // ─── Extraction batch ──────────────────────────────────────────────────────

    /**
     * POST /api/v1/extract/batch
     * Body: { "urls": ["https://...", "https://..."] }  (max 10)
     */
    public function extractBatch(Request $request): JsonResponse
    {
        $request->validate([
            'urls'   => ['required', 'array', 'min:1', 'max:10'],
            'urls.*' => ['required', 'url', 'max:2048'],
        ]);

        $urls = collect($request->input('urls'))->map(fn($u) => trim($u))->all();

        try {
            $response = Http::timeout(self::EXTRACT_TIMEOUT * 2) // plus long pour le batch
                ->post("{$this->extractorUrl}/extract/batch", ['urls' => $urls]);

            if ($response->failed()) {
                throw new \Exception("Erreur batch: " . $response->status());
            }

            $data = $response->json();

            // Normaliser chaque résultat
            if (isset($data['results'])) {
                $data['results'] = array_map(function ($result) {
                    if (($result['success'] ?? false) && isset($result['data'])) {
                        $result['data'] = $this->normalizeVideoData($result['data']);
                    }
                    return $result;
                }, $data['results']);
            }

            return response()->json($data);

        } catch (\Exception $e) {
            Log::error('WaziScope batch error', ['error' => $e->getMessage()]);
            return response()->json([
                'success'   => false,
                'message'   => 'Erreur lors de l\'extraction batch',
                'results'   => [],
                'total'     => count($urls),
                'succeeded' => 0,
                'failed'    => count($urls),
            ], 500);
        }
    }

    // ─── Proxy de téléchargement ───────────────────────────────────────────────

    /**
     * GET /api/v1/download?url=...&filename=...
     *
     * Proxifie le téléchargement pour contourner CORS et hotlink protection
     * sur iOS/Android WebView.
     */
    public function download(Request $request): StreamedResponse|JsonResponse
    {
        $request->validate([
            'url'      => ['required', 'url'],
            'filename' => ['nullable', 'string', 'max:255'],
        ]);

        $videoUrl = $request->input('url');
        $filename = $this->sanitizeFilename($request->input('filename', 'video_' . time() . '.mp4'));

        // ── Vérification de domaine ─────────────────────────────────────────
        if (! $this->isAllowedDomain($videoUrl)) {
            Log::warning('WaziScope: domaine non autorisé', ['url' => $videoUrl]);
            return response()->json([
                'success' => false,
                'message' => 'Source non autorisée',
            ], 403);
        }

        // ── Détecter le Content-Type selon l'extension ─────────────────────
        $ext         = strtolower(pathinfo(parse_url($videoUrl, PHP_URL_PATH) ?? '', PATHINFO_EXTENSION));
        $contentType = match ($ext) {
            'mp4'  => 'video/mp4',
            'webm' => 'video/webm',
            'm4a', 'mp3' => 'audio/mpeg',
            default => 'video/mp4',
        };

        return response()->streamDownload(function () use ($videoUrl) {
            $context = stream_context_create([
                'http' => [
                    'method'          => 'GET',
                    'follow_location' => true,
                    'max_redirects'   => 5,
                    'timeout'         => 90,
                    'header'          => implode("\r\n", [
                        'User-Agent: Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
                        'Accept: video/mp4,video/*;q=0.9,*/*;q=0.8',
                        'Accept-Language: fr-FR,fr;q=0.9,en;q=0.7',
                        'Referer: https://www.tiktok.com/',
                        'Range: bytes=0-',
                    ]),
                ],
                'ssl' => [
                    'verify_peer'      => true,
                    'verify_peer_name' => true,
                ],
            ]);

            $stream = @fopen($videoUrl, 'r', false, $context);

            if (! $stream) {
                Log::error('WaziScope: impossible d\'ouvrir le stream', ['url' => $videoUrl]);
                return;
            }

            try {
                while (! feof($stream)) {
                    $chunk = fread($stream, 65536); // 64KB chunks
                    if ($chunk === false) break;
                    echo $chunk;
                    if (ob_get_level() > 0) {
                        ob_flush();
                    }
                    flush();
                }
            } finally {
                fclose($stream);
            }
        }, $filename, [
            'Content-Type'        => $contentType,
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
            'Cache-Control'       => 'no-cache, no-store',
            'X-Accel-Buffering'   => 'no',
            'Transfer-Encoding'   => 'chunked',
        ]);
    }

    // ─── Helpers privés ────────────────────────────────────────────────────────

    /**
     * Normalise et enrichit les données VideoInfo renvoyées par Python v2
     */
    private function normalizeVideoData(array $data): array
    {
        return [
            'original_url'       => $data['original_url']       ?? '',
            'title'              => $data['title']               ?? 'Vidéo sans titre',
            'description'        => $data['description']         ?? null,
            'author'             => $data['author']              ?? null,
            'thumbnail'          => $data['thumbnail']           ?? null,
            'duration'           => $data['duration']            ?? null,
            'view_count'         => $data['view_count']          ?? null,
            'like_count'         => $data['like_count']          ?? null,
            'platform'           => $data['platform']            ?? 'unknown',
            'best_url'           => $data['best_url']            ?? null,
            'no_watermark_url'   => $data['no_watermark_url']    ?? null,
            'audio_only_url'     => $data['audio_only_url']      ?? null,
            'formats'            => $this->normalizeFormats($data['formats'] ?? []),
            // URL proxy Laravel (plus fiable sur mobile)
            'proxy_download_url' => $this->buildProxyUrl(
                $data['no_watermark_url'] ?? $data['best_url'] ?? '',
                $data['title'] ?? 'video'
            ),
        ];
    }

    /**
     * Normalise les formats pour le frontend
     */
    private function normalizeFormats(array $formats): array
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
            'proxy_url'    => $this->buildProxyUrl($fmt['url'] ?? '', ''),
        ], $formats);
    }

    /**
     * Construit l'URL proxy Laravel pour un download
     */
    private function buildProxyUrl(string $videoUrl, string $title): string
    {
        if (! $videoUrl) return '';

        return url('/api/v1/download') . '?' . http_build_query([
            'url'      => $videoUrl,
            'filename' => $this->sanitizeFilename($title) . '.mp4',
        ]);
    }

    /**
     * Vérifie qu'une URL de téléchargement provient d'un domaine autorisé
     */
    private function isAllowedDomain(string $url): bool
    {
        $host = strtolower(parse_url($url, PHP_URL_HOST) ?? '');
        if (! $host) return false;

        foreach (self::ALLOWED_PROXY_DOMAINS as $domain) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) {
                return true;
            }
        }

        return false;
    }

    /**
     * Nettoie un nom de fichier pour éviter les injections
     */
    private function sanitizeFilename(string $name): string
    {
        $name = preg_replace('/[^\w\-. ]/u', '_', $name);
        $name = preg_replace('/\s+/', '_', trim($name));
        return substr($name ?: 'video', 0, 100);
    }
}