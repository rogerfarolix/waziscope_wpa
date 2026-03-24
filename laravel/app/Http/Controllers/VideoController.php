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
    /**
     * URL du service FastAPI extractor
     */
    private string $extractorUrl;

    public function __construct()
    {
        $this->extractorUrl = config('services.waziscope.extractor_url', 'http://localhost:8032');
    }

    // ─── Extraction ────────────────────────────────────────────────────────────

    /**
     * POST /api/extract
     * Reçoit une URL vidéo, appelle FastAPI, retourne les infos
     */
    public function extract(Request $request): JsonResponse
    {
        $request->validate([
            'url' => ['required', 'url', 'max:2048'],
        ]);

        $url = $request->input('url');

        // Cache 10 minutes pour éviter les requêtes répétées
        $cacheKey = 'video_extract_' . md5($url);

        try {
            $data = Cache::remember($cacheKey, 600, function () use ($url) {
                $response = Http::timeout(30)
                    ->get("{$this->extractorUrl}/extract", ['url' => $url]);

                if ($response->failed()) {
                    throw new \Exception("Le service d'extraction a échoué: " . $response->status());
                }

                return $response->json();
            });

            if (!($data['success'] ?? false)) {
                return response()->json([
                    'success' => false,
                    'message' => $data['error'] ?? 'Extraction échouée',
                ], 422);
            }

            return response()->json([
                'success' => true,
                'data'    => $data['data'],
            ]);

        } catch (\Exception $e) {
            Log::error('WaziScope extract error', ['url' => $url, 'error' => $e->getMessage()]);

            return response()->json([
                'success' => false,
                'message' => 'Impossible d\'extraire cette vidéo. Vérifiez l\'URL.',
            ], 500);
        }
    }

    // ─── Proxy de téléchargement ────────────────────────────────────────────────

    /**
     * GET /api/download
     * Proxifie le téléchargement pour contourner CORS/hotlink sur mobile
     */
    public function download(Request $request): StreamedResponse|\Illuminate\Http\JsonResponse
    {
        $request->validate([
            'url'      => ['required', 'url'],
            'filename' => ['nullable', 'string', 'max:255'],
        ]);

        $videoUrl = $request->input('url');
        $filename = $request->input('filename', 'video_' . time() . '.mp4');

        // Sécurité : vérifier que l'URL vient d'une source connue
        $allowedDomains = [
            'tiktokcdn.com', 'tiktokv.com', 'byteoversea.com',
            'pinimg.com', 'pinterest.com',
            'fbcdn.net', 'facebook.com', 'fbsbx.com',
            'cdninstagram.com', 'instagram.com',
        ];

        $parsedUrl = parse_url($videoUrl);
        $host = $parsedUrl['host'] ?? '';

        $isAllowed = collect($allowedDomains)->contains(function ($domain) use ($host) {
            return str_ends_with($host, $domain);
        });

        if (!$isAllowed) {
            return response()->json(['message' => 'Source non autorisée'], 403);
        }

        return response()->streamDownload(function () use ($videoUrl) {
            $stream = fopen($videoUrl, 'r', false, stream_context_create([
                'http' => [
                    'method'          => 'GET',
                    'follow_location' => true,
                    'timeout'         => 60,
                    'header'          => [
                        'User-Agent: Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36',
                        'Referer: https://www.tiktok.com/',
                    ],
                ],
            ]));

            if ($stream) {
                while (!feof($stream)) {
                    echo fread($stream, 8192);
                    ob_flush();
                    flush();
                }
                fclose($stream);
            }
        }, $filename, [
            'Content-Type'              => 'video/mp4',
            'Content-Disposition'       => 'attachment; filename="' . $filename . '"',
            'Cache-Control'             => 'no-cache',
            'X-Accel-Buffering'         => 'no',
        ]);
    }

    // ─── Plateformes supportées ─────────────────────────────────────────────────

    public function platforms(): JsonResponse
    {
        try {
            $response = Http::timeout(5)->get("{$this->extractorUrl}/platforms");
            return response()->json($response->json());
        } catch (\Exception $e) {
            return response()->json([
                'platforms' => [
                    ['id' => 'tiktok',    'name' => 'TikTok',    'icon' => '🎵', 'no_watermark' => true],
                    ['id' => 'pinterest', 'name' => 'Pinterest', 'icon' => '📌', 'no_watermark' => false],
                    ['id' => 'facebook',  'name' => 'Facebook',  'icon' => '📘', 'no_watermark' => false],
                ]
            ]);
        }
    }
}
