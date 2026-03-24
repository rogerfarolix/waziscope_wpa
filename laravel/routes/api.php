<?php

use App\Http\Controllers\VideoController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| WaziScope API Routes
|--------------------------------------------------------------------------
*/

Route::prefix('v1')->group(function () {

    // Health check
    Route::get('/health', fn () => response()->json(['status' => 'ok', 'service' => 'waziscope-laravel']));

    // Plateformes supportées
    Route::get('/platforms', [VideoController::class, 'platforms']);

    // Extraction vidéo (reçoit l'URL, retourne les infos + lien de dl)
    Route::post('/extract', [VideoController::class, 'extract']);

    // Proxy de téléchargement (stream la vidéo via Laravel pour éviter CORS)
    Route::get('/download', [VideoController::class, 'download']);

});
