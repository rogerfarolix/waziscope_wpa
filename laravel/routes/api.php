<?php

use App\Http\Controllers\VideoController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| WaziScope API Routes — v3
|--------------------------------------------------------------------------
|
| Throttle par groupe :
|   - système  : 120 req/min (health, platforms, detect)
|   - extract  :  30 req/min (1 extraction toutes les 2s)
|   - download :  60 req/min (streaming)
|   - batch    :   5 req/min (batch / playlist coûteux)
*/

Route::prefix('v1')->group(function () {

    // ── Système (pas de limit stricte, mais on protège quand même) ────────────
    Route::middleware('throttle:120,1')->group(function () {
        Route::get('/health',       [VideoController::class, 'health']);
        Route::get('/platforms',    [VideoController::class, 'platforms']);
        Route::get('/capabilities', [VideoController::class, 'checkCapabilities']);
        Route::get('/detect',       [VideoController::class, 'detect']);
    });

    // ── Extraction (coûteux — limite à 30/min) ────────────────────────────────
    Route::middleware('throttle:30,1')->group(function () {
        Route::post('/extract',            [VideoController::class, 'extract']);
        Route::get('/progress/{jobId}',    [VideoController::class, 'progress']);
    });

    // ── Batch & Playlist (très coûteux — 5/min) ───────────────────────────────
    Route::middleware('throttle:5,1')->group(function () {
        Route::post('/extract/batch',      [VideoController::class, 'extractBatch']);
        Route::post('/extract/playlist',   [VideoController::class, 'extractPlaylist']);
    });

    // ── Proxy de téléchargement (60/min) ──────────────────────────────────────
    Route::middleware('throttle:60,1')->group(function () {
        Route::get('/download',  [VideoController::class, 'download']);
        Route::get('/strip',     [VideoController::class, 'stripMetadata']);
    });

});
