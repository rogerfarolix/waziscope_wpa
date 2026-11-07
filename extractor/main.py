"""
WaziScope - FastAPI Extractor Service v3.0
Nouvelles fonctionnalités:
  - Plateformes étendues: Dailymotion, Vimeo, Twitch, Rumble, Snapchat, Odysee
  - Support playlists YouTube (et autres)
  - Téléchargement longs métrages (pas de limite de durée)
  - Sélection de qualité par requête
  - Streaming SSE de progression via /extract/progress
  - Meilleure détection TikTok, Pinterest, Facebook
"""

from wz.core import *  # noqa: F401,F403  (config, schémas, helpers)
from wz.facebook import _extract_facebook
from wz.pinterest import _extract_pinterest
from wz.tiktok import _extract_tiktok
from wz.dailymotion import _extract_dailymotion
from wz.youtube import _strip_youtube_list, _youtube_via_invidious

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="WaziScope Extractor",
    description="Extraire les URLs de vidéos depuis TikTok, YouTube, Pinterest, Facebook, Instagram, LinkedIn, Twitter, Dailymotion, Vimeo, Twitch, Rumble, Odysee…",
    version="3.0.0",
)

# L'extractor est un service INTERNE uniquement accessible par Laravel via le
# loopback 127.0.0.1 (Supervisor). Pas de CORS nécessaire — aucun navigateur n'appelle ce service.


async def extract_video_info(url: str, quality: str = "best") -> VideoInfo:
    url      = url.strip()
    platform = detect_platform(url)

    if platform == "youtube":
        url = _strip_youtube_list(url)

    if platform == "unknown":
        raise ValueError(
            f"Plateforme non reconnue. Supportées : {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )

    if platform == "tiktok":
        return await _extract_tiktok(url)

    if platform == "pinterest":
        return await _extract_pinterest(url)

    if platform == "facebook":
        return await _extract_facebook(url)

    if platform == "dailymotion":
        return await _extract_dailymotion(url)


    ydl_opts = get_ydl_opts(platform, quality)
    loop     = asyncio.get_running_loop()

    def _sync_extract() -> dict:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)  # type: ignore

    try:
        info = await loop.run_in_executor(executor, _sync_extract)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "This video is private" in msg:
            raise ValueError("Cette vidéo est privée.")
        if "not available" in msg:
            raise ValueError("Cette vidéo n'est pas disponible dans votre région.")
        if "Sign in" in msg or "confirm you're not a bot" in msg or "bot" in msg.lower() and "sign" in msg.lower():
            if platform == "instagram":
                raise ValueError("Instagram requiert une connexion — seuls les profils publics sans restriction sont supportés.")
            if platform in ("twitter", "x"):
                raise ValueError("Twitter/X requiert une authentification API. Essayez avec une URL de tweet public avec vidéo.")
            if platform == "youtube":
                # Fallback automatique via Invidious (contourne le blocage IP datacenter)
                logger.warning(f"[youtube] Bot-detection — tentative fallback Invidious pour {url}")
                try:
                    return await _youtube_via_invidious(url, quality)
                except Exception as inv_err:
                    logger.error(f"[youtube] Invidious fallback échoué : {inv_err}")
                    raise ValueError(
                        "YouTube a bloqué l'accès à cette vidéo et le fallback Invidious a aussi échoué. "
                        "Vidéo peut-être supprimée, privée ou restreinte géographiquement."
                    )
            raise ValueError("Cette vidéo nécessite une connexion.")
        if "login" in msg.lower() or "authentication" in msg.lower() or "Account authentication" in msg:
            if platform == "youtube":
                logger.warning(f"[youtube] Auth requise — tentative fallback Invidious pour {url}")
                try:
                    return await _youtube_via_invidious(url, quality)
                except Exception as inv_err:
                    logger.error(f"[youtube] Invidious fallback échoué : {inv_err}")
            raise ValueError("Cette vidéo nécessite une connexion.")
        if "removed" in msg.lower() or "deleted" in msg.lower():
            raise ValueError("Cette vidéo a été supprimée.")
        if "members only" in msg.lower():
            raise ValueError("Contenu réservé aux membres.")
        if "age" in msg.lower() and ("restrict" in msg.lower() or "gate" in msg.lower()):
            raise ValueError("Cette vidéo est restreinte aux adultes (connexion requise).")
        if "unavailable" in msg.lower() and platform == "youtube":
            raise ValueError("Cette vidéo YouTube n'est pas disponible (privée, supprimée ou restreinte géographiquement).")
        raise ValueError(_friendly_error(msg, platform))
    except Exception as e:
        logger.exception(f"[{platform}] Erreur inattendue")
        raise ValueError(_friendly_error(str(e), platform))

    if not info:
        raise ValueError("Aucune information trouvée.")

    # Gérer les playlists retournées par yt-dlp
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if entries:
            first_entry = entries[0]
            if isinstance(first_entry, dict) and first_entry.get("url"):
                info = first_entry
            else:
                raise ValueError("Playlist détectée — utilisez /extract/playlist pour les playlists.")

    formats, best_url, no_watermark_url, audio_only_url = _parse_formats(info, platform)
    required_headers = DOWNLOAD_HEADERS.get(platform, {})

    return VideoInfo(
        original_url=url,
        title=info.get("title") or "Vidéo sans titre",
        description=info.get("description"),
        author=info.get("uploader") or info.get("creator") or info.get("channel"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        platform=platform,
        formats=formats,
        best_url=best_url,
        no_watermark_url=no_watermark_url,
        audio_only_url=audio_only_url,
        required_headers=required_headers,
    )


# ─── Extraction playlist ──────────────────────────────────────────────────────

async def extract_playlist_info(url: str, limit: int = 20) -> PlaylistResponse:
    platform = detect_platform(url)
    loop     = asyncio.get_running_loop()

    flat_opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "socket_timeout": 30,
        "playlistend": limit,
        "js_runtimes": {"node": {"path": "/usr/bin/node"}},
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
            }
        },
    }
    if _COOKIES_PATH:
        flat_opts["cookiefile"] = _COOKIES_PATH

    def _get_flat():
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        flat = await loop.run_in_executor(executor, _get_flat)
    except Exception as e:
        raise ValueError(f"Impossible de charger la playlist : {e}")

    if not flat:
        raise ValueError("Playlist introuvable ou vide.")

    entries = flat.get("entries") or []
    playlist_title = flat.get("title") or flat.get("playlist_title") or "Playlist"

    # Limiter la concurrence au nombre de workers du ThreadPoolExecutor
    _semaphore = asyncio.Semaphore(executor._max_workers)

    async def _extract_entry(i: int, entry: dict) -> PlaylistItem:
        entry_url = entry.get("url") or entry.get("webpage_url") or ""
        if not entry_url.startswith("http"):
            entry_url = f"https://www.youtube.com/watch?v={entry.get('id', '')}"
        async with _semaphore:
            try:
                info = await extract_video_info(entry_url)
                return PlaylistItem(index=i, success=True, data=info)
            except Exception as e:
                return PlaylistItem(index=i, success=False, error=str(e))

    tasks = [_extract_entry(i, e) for i, e in enumerate(entries[:limit])]
    items = await asyncio.gather(*tasks, return_exceptions=False)

    return PlaylistResponse(
        success=True,
        playlist_title=playlist_title,
        total=len(entries),
        items=list(items),
    )


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Système"])
async def health():
    return {
        "status": "ok",
        "service": "waziscope-extractor",
        "version": "3.0.0",
        "yt_dlp_version": yt_dlp.version.__version__,
        "supported_platforms": sorted(SUPPORTED_PLATFORMS),
    }


_SMOKE_STATE = _os.path.join(_os.path.dirname(__file__), ".smoke_state.json")


@app.get("/status", tags=["Système"])
async def platform_status():
    """État par plateforme issu du dernier smoke_test.py (true = OK)."""
    try:
        with open(_SMOKE_STATE) as f:
            platforms = json.load(f)
        checked_at = _os.path.getmtime(_SMOKE_STATE)
    except Exception:
        platforms, checked_at = {}, None
    return {"platforms": platforms, "checked_at": checked_at}


@app.get("/platforms", tags=["Système"])
async def get_platforms():
    return {
        "platforms": [
            {"id": "tiktok",      "name": "TikTok",       "no_watermark": True,  "notes": "Sans watermark via API mobile"},
            {"id": "youtube",     "name": "YouTube",       "no_watermark": False, "notes": "HD jusqu'à 4K, playlists supportées"},
            {"id": "pinterest",   "name": "Pinterest",     "no_watermark": False, "notes": "MP4 direct (scraper intégré)"},
            {"id": "facebook",    "name": "Facebook",      "no_watermark": False, "notes": "Vidéos & Reels publics"},
            {"id": "instagram",   "name": "Instagram",     "no_watermark": False, "notes": "Reels & posts publics"},
            {"id": "linkedin",    "name": "LinkedIn",      "no_watermark": False, "notes": "Vidéos natives"},
            {"id": "twitter",     "name": "Twitter/X",     "no_watermark": False, "notes": "Vidéos tweets"},
            {"id": "dailymotion", "name": "Dailymotion",   "no_watermark": False, "notes": "Toutes qualités"},
            {"id": "vimeo",       "name": "Vimeo",         "no_watermark": False, "notes": "HD jusqu'à 4K"},
            {"id": "twitch",      "name": "Twitch",        "no_watermark": False, "notes": "Clips & VODs"},
            {"id": "rumble",      "name": "Rumble",        "no_watermark": False, "notes": "Toutes qualités"},
            {"id": "odysee",      "name": "Odysee",        "no_watermark": False, "notes": "Vidéos LBRY/Odysee"},
            {"id": "snapchat",    "name": "Snapchat",      "no_watermark": False, "notes": "Spotlight publics"},
            {"id": "bilibili",    "name": "Bilibili",      "no_watermark": False, "notes": "Vidéos chinoises"},
        ]
    }


@app.get("/extract", response_model=ExtractResponse, tags=["Extraction"])
async def extract(
    url:     str = Query(..., description="URL de la vidéo"),
    quality: str = Query("best", description="Qualité: best, 1080, 720, 480, 4k, audio"),
):
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL invalide")

    start = time.monotonic()
    try:
        logger.info(f"Extraction [{quality}] → {url}")
        info    = await extract_video_info(url, quality)
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.info(f"OK [{info.platform}] '{info.title[:60]}' — {elapsed}ms")
        return ExtractResponse(success=True, data=info, duration_ms=elapsed)
    except ValueError as e:
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.warning(f"Extraction échouée : {e}")
        return ExtractResponse(success=False, error=str(e), duration_ms=elapsed)
    except Exception as e:
        logger.error(f"Erreur interne : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur. Consultez les logs.")


@app.post("/extract/batch", response_model=BatchResponse, tags=["Extraction"])
async def extract_batch(body: BatchRequest):
    tasks     = [extract_video_info(url.strip()) for url in body.urls]
    raw       = await asyncio.gather(*tasks, return_exceptions=True)
    results   = []
    succeeded = failed = 0
    for r in raw:
        if isinstance(r, Exception):
            results.append(ExtractResponse(success=False, error=str(r)))
            failed += 1
        else:
            results.append(ExtractResponse(success=True, data=r))
            succeeded += 1
    return BatchResponse(
        success=failed == 0, results=results,
        total=len(body.urls), succeeded=succeeded, failed=failed,
    )


@app.post("/extract/playlist", response_model=PlaylistResponse, tags=["Extraction"])
async def extract_playlist_endpoint(body: PlaylistRequest):
    url = body.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL invalide")

    platform = detect_platform(url)
    if platform not in PLAYLIST_PLATFORMS:
        raise HTTPException(
            status_code=422,
            detail=f"Les playlists ne sont pas supportées pour {platform if platform != 'unknown' else 'cette plateforme'}"
        )

    try:
        return await extract_playlist_info(url, body.limit)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Playlist error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur. Consultez les logs.")


@app.get("/extract/progress/{job_id}", tags=["Extraction"])
async def extract_with_progress(job_id: str, url: str = Query(...), quality: str = Query("best")):
    """
    SSE endpoint — envoie la progression de l'extraction en temps réel.
    Utile pour les longs métrages ou vidéos > 30 min.
    """
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL invalide")

    _progress_store[job_id] = {"status": "starting", "percent": 0}

    async def _run_and_stream():
        try:
            _progress_store[job_id] = {"status": "extracting", "percent": 10}
            yield f"data: {json.dumps(_progress_store[job_id])}\n\n"

            info = await extract_video_info(url, quality)
            _progress_store[job_id] = {
                "status": "done",
                "percent": 100,
                "data": info.model_dump(),
            }
            yield f"data: {json.dumps({'status': 'done', 'percent': 100, 'data': info.model_dump()})}\n\n"
        except Exception as e:
            _progress_store[job_id] = {"status": "error", "error": str(e)}
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
        finally:
            # Nettoyer après 5 min
            await asyncio.sleep(300)
            _progress_store.pop(job_id, None)

    return StreamingResponse(
        _run_and_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/detect", tags=["Utilitaires"])
async def detect(url: str = Query(...)):
    p = detect_platform(url.strip())
    return {
        "url": url,
        "platform": p,
        "supported": p in SUPPORTED_PLATFORMS,
        "supports_playlist": p in PLAYLIST_PLATFORMS,
    }


@app.get("/headers/{platform}", tags=["Utilitaires"])
async def get_download_headers(platform: str):
    headers = DOWNLOAD_HEADERS.get(platform, {})
    return {"platform": platform, "headers": headers}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8032, reload=True, log_level="info")
