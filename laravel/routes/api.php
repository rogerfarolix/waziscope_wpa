<?php

use App\Http\Controllers\VideoController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| WaziScope API Routes — v3
|--------------------------------------------------------------------------
*/

Route::prefix('v1')->group(function () {

    // ── Système ────────────────────────────────────────────────────────────
    Route::get('/health',        [VideoController::class, 'health']);
    Route::get('/platforms',     [VideoController::class, 'platforms']);
    Route::get('/capabilities',  [VideoController::class, 'checkCapabilities']);

    // Détection plateforme rapide (sans extraction)
    Route::get('/detect',        [VideoController::class, 'detect']);

    // ── Extraction ─────────────────────────────────────────────────────────
    Route::post('/extract',        [VideoController::class, 'extract']);
    Route::post('/extract/batch',  [VideoController::class, 'extractBatch']);

    // Playlist
    Route::post('/extract/playlist', [VideoController::class, 'extractPlaylist']);

    // Progression SSE (long videos)
    Route::get('/progress/{jobId}',  [VideoController::class, 'progress']);

    // ── Proxy de téléchargement ────────────────────────────────────────────
    Route::get('/download',  [VideoController::class, 'download']);

    // Strip metadata via ffmpeg
    Route::get('/strip',     [VideoController::class, 'stripMetadata']);

});
