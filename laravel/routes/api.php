<?php

use App\Http\Controllers\VideoController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| WaziScope API Routes — v2
|--------------------------------------------------------------------------
*/

Route::prefix('v1')->group(function () {

    // ── Système ────────────────────────────────────────────────────────────
    Route::get('/health',    [VideoController::class, 'health']);
    Route::get('/platforms', [VideoController::class, 'platforms']);

    // Détection plateforme rapide (sans extraction)
    Route::get('/detect',    [VideoController::class, 'detect']);

    // ── Extraction ─────────────────────────────────────────────────────────
    Route::post('/extract',        [VideoController::class, 'extract']);
    Route::post('/extract/batch',  [VideoController::class, 'extractBatch']);

    // ── Proxy de téléchargement ────────────────────────────────────────────
    Route::get('/download',  [VideoController::class, 'download']);

});
