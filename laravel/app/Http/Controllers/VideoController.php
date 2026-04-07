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

    private const CACHE_TTL       = 600;  // 10 min
    private const EXTRACT_TIMEOUT = 60;
    private const FAST_TIMEOUT    = 5;

    private const ALLOWED_PROXY_DOMAINS = [
        'tiktokcdn.com', 'tiktokv.com', 'tiktokcdn-us.com',
        'tiktokcdn-eu.com', 'byteoversea.com', 'tiktok.com',
        'musical.ly', 'p16-sign.tiktokcdn-us.com',
        'pinimg.com', 'pinterest.com',
        'fbcdn.net', 'facebook.com', 'fbsbx.com',
        'cdninstagram.com', 'instagram.com',
        'googlevideo.com', 'youtube.com', 'ytimg.com',
        'licdn.com', 'linkedin.com',
        'twimg.com', 'twitter.com', 'x.com',
        'akamaihd.net', 'cloudfront.net', 'akamai.net',
    ];

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

        // Vérifier la disponibilité de ffmpeg
        $ffmpegPath = $this->getFfmpegPath();

        return response()->json([
            'status'   => 'ok',
            'service'  => 'waziscope-laravel',
            'extractor' => $python,
            'ffmpeg'   => $ffmpegPath ? ['available' => true, 'path' => $ffmpegPath] : ['available' => false],
        ]);
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
                'success'      => true,
                'data'         => $this->normalizeVideoData($data['data']),
                'duration_ms'  => $data['duration_ms'] ?? null,
                'ffmpeg_available' => (bool) $this->getFfmpegPath(),
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

        if (!$this->isAllowedDomain($videoUrl)) {
            return response()->json(['success' => false, 'message' => 'Source non autorisée'], 403);
        }

        if (!function_exists('curl_init')) {
            return $this->downloadWithFopen($videoUrl, $filename, $platform);
        }

        return $this->downloadWithCurl($videoUrl, $filename, $platform);
    }

    // ─── Strip metadata ────────────────────────────────────────────────────────
    //
    // Télécharge la vidéo depuis le CDN, passe par ffmpeg pour supprimer
    // TOUTES les métadonnées (titre, auteur, GPS, device info, description,
    // copyright, dates EXIF, etc.) sans re-encoder (-c copy = ultra rapide).
    //
    // ffmpeg -i input.mp4 -map_metadata -1 -map_metadata:s:v -1
    //        -map_metadata:s:a -1 -c copy output.mp4

    public function stripMetadata(Request $request): StreamedResponse|JsonResponse
    {
        $request->validate([
            'url'      => ['required', 'url'],
            'filename' => ['nullable', 'string', 'max:255'],
            'platform' => ['nullable', 'string', 'max:30'],
        ]);

        $videoUrl = $request->input('url');
        $platform = $request->input('platform', $this->detectPlatformFromUrl($videoUrl));
        $baseName = $this->sanitizeFilename(
            $request->input('filename', 'video_' . time())
        );
        $filename = $baseName . '_clean.mp4';

        // Sécurité domaine
        if (!$this->isAllowedDomain($videoUrl)) {
            Log::warning('WaziScope strip: domaine non autorisé', ['url' => $videoUrl]);
            return response()->json(['success' => false, 'message' => 'Source non autorisée'], 403);
        }

        // Vérifier ffmpeg
        $ffmpegBin = $this->getFfmpegPath();
        if (!$ffmpegBin) {
            return response()->json([
                'success' => false,
                'message' => 'ffmpeg n\'est pas installé sur ce serveur. Contactez l\'administrateur.',
            ], 503);
        }

        if (!function_exists('curl_init')) {
            return response()->json(['success' => false, 'message' => 'cURL requis'], 503);
        }

        $headers  = self::PLATFORM_DOWNLOAD_HEADERS[$platform] ?? self::PLATFORM_DOWNLOAD_HEADERS['tiktok'];
        $tmpDir   = sys_get_temp_dir();
        $uniqueId = uniqid('wzs_', true);
        $tmpInput  = $tmpDir . DIRECTORY_SEPARATOR . $uniqueId . '_in.mp4';
        $tmpOutput = $tmpDir . DIRECTORY_SEPARATOR . $uniqueId . '_out.mp4';

        // ── Étape 1 : télécharger la vidéo dans un fichier temporaire ─────────
        $dlSuccess = $this->curlDownloadToFile($videoUrl, $headers, $tmpInput);

        if (!$dlSuccess || !file_exists($tmpInput) || filesize($tmpInput) === 0) {
            @unlink($tmpInput);
            Log::warning('WaziScope strip: download échoué', ['url' => substr($videoUrl, 0, 100)]);
            return response()->json([
                'success' => false,
                'message' => 'Impossible de télécharger la vidéo. L\'URL a peut-être expiré.',
            ], 410);
        }

        // ── Étape 2 : suppression des métadonnées via ffmpeg ──────────────────
        $cmd = sprintf(
            '%s -y -i %s -map_metadata -1 -map_metadata:s:v -1 -map_metadata:s:a -1 -c copy %s 2>/dev/null',
            escapeshellarg($ffmpegBin),
            escapeshellarg($tmpInput),
            escapeshellarg($tmpOutput)
        );

        exec($cmd, $ffOutput, $ffCode);

        @unlink($tmpInput); // Nettoyer l'input dès que possible

        if ($ffCode !== 0 || !file_exists($tmpOutput) || filesize($tmpOutput) === 0) {
            @unlink($tmpOutput);
            Log::error('WaziScope strip: ffmpeg failed', ['code' => $ffCode]);
            return response()->json([
                'success' => false,
                'message' => 'Erreur lors de la suppression des métadonnées.',
            ], 500);
        }

        $fileSize = filesize($tmpOutput);
        Log::info("WaziScope strip: OK [{$platform}] {$fileSize} bytes → {$filename}");

        // ── Étape 3 : streamer le fichier propre, puis nettoyer ───────────────
        return response()->streamDownload(
            function () use ($tmpOutput) {
                $f = @fopen($tmpOutput, 'rb');
                if ($f) {
                    try {
                        while (!feof($f)) {
                            $chunk = fread($f, 65536);
                            if ($chunk === false) break;
                            echo $chunk;
                            if (ob_get_level() > 0) ob_flush();
                            flush();
                        }
                    } finally {
                        fclose($f);
                        @unlink($tmpOutput);
                    }
                }
            },
            $filename,
            [
                'Content-Type'        => 'video/mp4',
                'Content-Disposition' => 'attachment; filename="' . $filename . '"',
                'Content-Length'      => (string) $fileSize,
                'Cache-Control'       => 'no-cache, no-store, must-revalidate',
                'X-Accel-Buffering'   => 'no',
                'X-Metadata-Stripped' => 'true',
            ]
        );
    }

    // ─── Check ffmpeg capability (API endpoint) ────────────────────────────────

    public function checkCapabilities(): JsonResponse
    {
        return response()->json([
            'ffmpeg' => (bool) $this->getFfmpegPath(),
        ]);
    }

    // ─── Private helpers ────────────────────────────────────────────────────────

    /**
     * Retourne le chemin de ffmpeg ou null s'il n'est pas disponible.
     */
    private function getFfmpegPath(): ?string
    {
        // Priorité : config > PATH auto-détecté
        $configured = config('services.waziscope.ffmpeg_path');
        if ($configured && file_exists($configured) && is_executable($configured)) {
            return $configured;
        }

        // Auto-détection (Linux/Mac)
        foreach (['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg'] as $path) {
            if (file_exists($path) && is_executable($path)) {
                return $path;
            }
        }

        // Fallback which
        $which = trim(shell_exec('which ffmpeg 2>/dev/null') ?? '');
        return $which ?: null;
    }

    /**
     * Télécharge une URL dans un fichier local avec cURL.
     * Retourne true si le téléchargement a réussi.
     */
    private function curlDownloadToFile(string $url, array $headers, string $destPath): bool
    {
        $fp = @fopen($destPath, 'wb');
        if (!$fp) return false;

        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL            => $url,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS      => 5,
            CURLOPT_TIMEOUT        => 180,     // 3 min max pour gros fichiers
            CURLOPT_CONNECTTIMEOUT => 15,
            CURLOPT_HTTPHEADER     => $this->formatCurlHeaders($headers),
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_ENCODING       => '',
            CURLOPT_FILE           => $fp,
            CURLOPT_HEADER         => false,
        ]);

        curl_exec($ch);
        $httpCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error    = curl_error($ch);
        curl_close($ch);
        fclose($fp);

        if ($error) {
            Log::warning('WaziScope curlDownloadToFile error', ['error' => $error]);
            return false;
        }

        return $httpCode >= 200 && $httpCode < 400;
    }

    /**
     * Download via cURL — streaming direct vers le navigateur.
     */
    private function downloadWithCurl(string $videoUrl, string $filename, string $platform): StreamedResponse|JsonResponse
    {
        $ext         = strtolower(pathinfo(parse_url($videoUrl, PHP_URL_PATH) ?? '', PATHINFO_EXTENSION));
        $contentType = match ($ext) {
            'webm'  => 'video/webm',
            'm4a'   => 'audio/mp4',
            'mp3'   => 'audio/mpeg',
            default => 'video/mp4',
        };

        $headers     = self::PLATFORM_DOWNLOAD_HEADERS[$platform] ?? self::PLATFORM_DOWNLOAD_HEADERS['tiktok'];
        $checkResult = $this->curlHead($videoUrl, $headers);

        if ($checkResult['http_code'] >= 400 && $checkResult['http_code'] !== 0) {
            return response()->json([
                'success' => false,
                'message' => "L'URL vidéo a expiré (code {$checkResult['http_code']}). Veuillez extraire à nouveau.",
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
                    CURLOPT_ENCODING       => '',
                    CURLOPT_BUFFERSIZE     => 65536,
                    CURLOPT_WRITEFUNCTION  => function ($ch, $data) {
                        echo $data;
                        if (ob_get_level() > 0) ob_flush();
                        flush();
                        return strlen($data);
                    },
                    CURLOPT_HEADER         => false,
                    CURLOPT_RETURNTRANSFER => false,
                ]);
                curl_exec($ch);
                $error = curl_error($ch);
                curl_close($ch);
                if ($error) Log::error('WaziScope cURL stream error', ['error' => $error]);
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
        $headers     = self::PLATFORM_DOWNLOAD_HEADERS[$platform] ?? [];
        $httpHeaders = array_map(fn($k, $v) => "$k: $v", array_keys($headers), array_values($headers));
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
            'Content-Type'        => 'video/mp4',
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
            'Cache-Control'       => 'no-cache',
            'X-Accel-Buffering'   => 'no',
        ]);
    }

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
        $result = ['http_code' => (int) curl_getinfo($ch, CURLINFO_HTTP_CODE), 'error' => curl_error($ch)];
        curl_close($ch);
        return $result;
    }

    private function formatCurlHeaders(array $headers): array
    {
        return array_map(fn($k, $v) => "$k: $v", array_keys($headers), array_values($headers));
    }

    private function detectPlatformFromUrl(string $url): string
    {
        $url = strtolower($url);
        if (str_contains($url, 'tiktok'))                                          return 'tiktok';
        if (str_contains($url, 'youtu'))                                           return 'youtube';
        if (str_contains($url, 'pinterest') || str_contains($url, 'pinimg'))       return 'pinterest';
        if (str_contains($url, 'facebook') || str_contains($url, 'fbcdn'))         return 'facebook';
        if (str_contains($url, 'instagram') || str_contains($url, 'cdninstagram')) return 'instagram';
        if (str_contains($url, 'linkedin') || str_contains($url, 'licdn'))         return 'linkedin';
        if (str_contains($url, 'twitter') || str_contains($url, 'twimg'))          return 'twitter';
        return 'tiktok';
    }

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
            'proxy_download_url' => $this->buildProxyUrl($bestUrl, $data['title'] ?? 'video', $platform),
            'proxy_strip_url'    => $this->buildStripUrl($bestUrl, $data['title'] ?? 'video', $platform),
        ];
    }

    private function normalizeFormats(array $formats, string $platform): array
    {
        return array_map(fn($fmt) => [
            'format_id'    => $fmt['format_id']   ?? 'unknown',
            'ext'          => $fmt['ext']          ?? 'mp4',
            'quality'      => $fmt['quality']      ?? '?',
            'url'          => $fmt['url']          ?? '',
            'filesize'     => $fmt['filesize']     ?? null,
            'width'        => $fmt['width']        ?? null,
            'height'       => $fmt['height']       ?? null,
            'fps'          => $fmt['fps']          ?? null,
            'vcodec'       => $fmt['vcodec']       ?? null,
            'acodec'       => $fmt['acodec']       ?? null,
            'no_watermark' => $fmt['no_watermark'] ?? false,
            'proxy_url'    => $this->buildProxyUrl($fmt['url'] ?? '', '', $platform),
            'strip_url'    => $this->buildStripUrl($fmt['url'] ?? '', '', $platform),
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

    private function buildStripUrl(string $videoUrl, string $title, string $platform = ''): string
    {
        if (!$videoUrl) return '';
        return url('/api/v1/strip') . '?' . http_build_query([
            'url'      => $videoUrl,
            'filename' => $this->sanitizeFilename($title ?: 'video'),
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
