"""
WaziScope - FastAPI Extractor Service v2.0
Téléchargeur robuste pour TikTok (sans watermark), Pinterest, Facebook, YouTube, LinkedIn
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import yt_dlp
import asyncio
import re
import time
import logging
from typing import Optional, Any
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("waziscope")

# Thread pool dédié aux opérations yt-dlp (bloquantes)
executor = ThreadPoolExecutor(max_workers=4)

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="WaziScope Extractor",
    description="Extraire les URLs de vidéos depuis TikTok, Pinterest, Facebook, YouTube, LinkedIn",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restreindre en production à ton domaine Laravel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schémas ──────────────────────────────────────────────────────────────────

class FormatInfo(BaseModel):
    format_id: str
    ext: str
    quality: Any
    url: str
    filesize: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    no_watermark: bool = False


class VideoInfo(BaseModel):
    original_url: str
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    platform: str
    formats: list[FormatInfo] = []
    best_url: Optional[str] = None
    no_watermark_url: Optional[str] = None
    audio_only_url: Optional[str] = None


class ExtractResponse(BaseModel):
    success: bool
    data: Optional[VideoInfo] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


class BatchRequest(BaseModel):
    urls: list[str]

    @field_validator("urls")
    @classmethod
    def limit_urls(cls, v):
        if len(v) > 10:
            raise ValueError("Maximum 10 URLs par requête batch")
        return v


class BatchResponse(BaseModel):
    success: bool
    results: list[ExtractResponse] = []
    total: int
    succeeded: int
    failed: int


# ─── Détection de plateforme ──────────────────────────────────────────────────

PLATFORM_PATTERNS: dict[str, str] = {
    "tiktok":    r"(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)",
    "youtube":   r"(youtube\.com|youtu\.be|youtube-nocookie\.com|music\.youtube\.com)",
    "pinterest": r"(pinterest\.(com|fr|ca|co\.\w+|at|de|es|pt|ru|ch|it|nz|au|co\.uk)|pin\.it)",
    "facebook":  r"(facebook\.com|fb\.com|fb\.watch|m\.facebook\.com)",
    "instagram": r"(instagram\.com|instagr\.am)",
    "linkedin":  r"(linkedin\.com|lnkd\.in)",
    "twitter":   r"(twitter\.com|t\.co|x\.com)",
}

SUPPORTED_PLATFORMS = {"tiktok", "youtube", "pinterest", "facebook", "instagram", "linkedin", "twitter"}


def detect_platform(url: str) -> str:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return "unknown"


# ─── User-Agents réalistes ─────────────────────────────────────────────────────

USER_AGENTS = {
    "desktop": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "mobile": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Mobile/15E148 Safari/604.1"
    ),
}


# ─── Options yt-dlp par plateforme ────────────────────────────────────────────

def get_ydl_opts(platform: str) -> dict:
    """Retourne les options yt-dlp optimisées pour chaque plateforme."""

    base: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": USER_AGENTS["desktop"],
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Mode": "navigate",
        },
        # Ignorer les erreurs de certificat SSL (utile en certains environnements)
        "nocheckcertificate": False,
    }

    if platform == "tiktok":
        base.update({
            # On récupère TOUS les formats pour pouvoir choisir le sans-watermark
            "format": "bestvideo+bestaudio/best",
            "extractor_args": {
                "tiktok": {
                    # Forcer le téléchargement via l'app mobile (sans watermark)
                    "webpage_download": ["1"],
                    "api_hostname": ["api22-normal-c-useast2a.tiktokv.com"],
                    "app_name": ["trill"],
                    "app_version": ["34.1.2"],
                    "manifest_app_version": ["341"],
                }
            },
            "http_headers": {
                **base["http_headers"],
                "User-Agent": USER_AGENTS["mobile"],
                "Referer": "https://www.tiktok.com/",
            },
        })

    elif platform == "youtube":
        base.update({
            # mp4 720p max pour ne pas surcharger, ajustable
            "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "extractor_args": {
                "youtube": {
                    "skip": ["dash", "hls"],  # Préférer les formats directs
                    "player_skip": ["configs", "webpage"],
                }
            },
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.youtube.com/",
            },
        })

    elif platform == "pinterest":
        base.update({
            "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.pinterest.com/",
            },
        })

    elif platform == "facebook":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "User-Agent": USER_AGENTS["mobile"],  # Facebook préfère mobile
                "Referer": "https://www.facebook.com/",
            },
        })

    elif platform == "instagram":
        base.update({
            "format": "best[ext=mp4]/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.instagram.com/",
            },
        })

    elif platform == "linkedin":
        base.update({
            "format": "best[ext=mp4]/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.linkedin.com/",
            },
        })

    elif platform == "twitter":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://twitter.com/",
            },
        })

    else:
        base.update({"format": "best[ext=mp4]/best"})

    return base


# ─── Helpers de parsing ───────────────────────────────────────────────────────

def _is_no_watermark_format(fmt: dict, platform: str) -> bool:
    """Détecte si un format TikTok est sans watermark."""
    if platform != "tiktok":
        return False

    fmt_id = (fmt.get("format_id") or "").lower()
    fmt_note = (fmt.get("format_note") or "").lower()
    fmt_url = (fmt.get("url") or "").lower()

    no_wm_signals = ["no_watermark", "nowm", "non_watermark", "download", "play_addr"]
    wm_signals = ["watermark", "wm_video", "wm"]

    # Si explicitement marqué sans watermark
    for signal in no_wm_signals:
        if signal in fmt_id or signal in fmt_note or signal in fmt_url:
            return True

    # Si contient un signal watermark → ce n'est PAS le bon format
    for signal in wm_signals:
        if signal in fmt_id or signal in fmt_note:
            return False

    return False


def _parse_formats(info: dict, platform: str) -> tuple[list[FormatInfo], str | None, str | None, str | None]:
    """
    Parse les formats yt-dlp en FormatInfo propres.
    Retourne (formats, best_url, no_watermark_url, audio_only_url)
    """
    formats: list[FormatInfo] = []
    best_url: str | None = None
    no_watermark_url: str | None = None
    audio_only_url: str | None = None

    raw_formats = info.get("formats") or []

    for fmt in raw_formats:
        raw_url = fmt.get("url") or fmt.get("manifest_url")
        if not raw_url:
            continue

        vcodec = fmt.get("vcodec") or ""
        acodec = fmt.get("acodec") or ""
        height = fmt.get("height")
        is_video = vcodec not in ("none", "", None)
        is_audio = acodec not in ("none", "", None)
        is_audio_only = not is_video and is_audio
        no_wm = _is_no_watermark_format(fmt, platform)

        entry = FormatInfo(
            format_id=fmt.get("format_id") or "unknown",
            ext=fmt.get("ext") or "mp4",
            quality=fmt.get("format_note") or height or "?",
            url=raw_url,
            filesize=fmt.get("filesize") or fmt.get("filesize_approx"),
            width=fmt.get("width"),
            height=height,
            fps=fmt.get("fps"),
            vcodec=vcodec or None,
            acodec=acodec or None,
            no_watermark=no_wm,
        )
        formats.append(entry)

        if is_audio_only and not audio_only_url:
            audio_only_url = raw_url

        if no_wm:
            no_watermark_url = raw_url

    # Meilleure URL vidéo = dernier format avec vidéo (yt-dlp trie qualité croissante)
    video_formats = [f for f in formats if f.vcodec and f.vcodec not in ("none", "")]
    if video_formats:
        best_url = video_formats[-1].url
    elif formats:
        best_url = formats[-1].url

    # Fallback si pas de no_watermark_url détectée pour TikTok
    if platform == "tiktok" and not no_watermark_url and best_url:
        no_watermark_url = best_url

    # Cas simple : yt-dlp retourne une seule URL directe
    if not formats and "url" in info:
        single_url = info["url"]
        formats = [FormatInfo(
            format_id="default",
            ext="mp4",
            quality="best",
            url=single_url,
        )]
        best_url = single_url
        no_watermark_url = single_url

    return formats, best_url, no_watermark_url, audio_only_url


# ─── Extraction principale ────────────────────────────────────────────────────

async def extract_video_info(url: str) -> VideoInfo:
    platform = detect_platform(url)

    if platform == "unknown":
        raise ValueError(
            f"Plateforme non reconnue. Supportées : {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )

    ydl_opts = get_ydl_opts(platform)
    loop = asyncio.get_event_loop()

    def _sync_extract() -> dict:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)  # type: ignore

    try:
        info = await loop.run_in_executor(executor, _sync_extract)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        # Messages d'erreur lisibles
        if "This video is private" in msg:
            raise ValueError("Cette vidéo est privée.")
        if "This video is not available" in msg:
            raise ValueError("Cette vidéo n'est pas disponible dans votre région.")
        if "Sign in" in msg or "login" in msg.lower():
            raise ValueError("Cette vidéo nécessite une connexion (contenu privé/réservé).")
        if "removed" in msg.lower() or "deleted" in msg.lower():
            raise ValueError("Cette vidéo a été supprimée.")
        raise ValueError(f"Impossible d'extraire la vidéo : {msg}")
    except Exception as e:
        raise ValueError(f"Erreur inattendue lors de l'extraction : {str(e)}")

    if not info:
        raise ValueError("Aucune information trouvée pour cette URL.")

    formats, best_url, no_watermark_url, audio_only_url = _parse_formats(info, platform)

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
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Système"])
async def health():
    """Vérification de l'état du service."""
    return {
        "status": "ok",
        "service": "waziscope-extractor",
        "version": "2.0.0",
        "yt_dlp_version": yt_dlp.version.__version__,
    }


@app.get("/platforms", tags=["Système"])
async def get_platforms():
    """Retourne les plateformes supportées avec leurs capacités."""
    return {
        "platforms": [
            {"id": "tiktok",    "name": "TikTok",     "icon": "🎵", "no_watermark": True,  "notes": "Sans watermark via API mobile"},
            {"id": "youtube",   "name": "YouTube",    "icon": "▶️",  "no_watermark": False, "notes": "HD jusqu'à 1080p"},
            {"id": "pinterest", "name": "Pinterest",  "icon": "📌", "no_watermark": False, "notes": "MP4 direct"},
            {"id": "facebook",  "name": "Facebook",   "icon": "📘", "no_watermark": False, "notes": "Vidéos publiques"},
            {"id": "instagram", "name": "Instagram",  "icon": "📸", "no_watermark": False, "notes": "Reels & posts publics"},
            {"id": "linkedin",  "name": "LinkedIn",   "icon": "💼", "no_watermark": False, "notes": "Vidéos natives"},
            {"id": "twitter",   "name": "Twitter/X",  "icon": "🐦", "no_watermark": False, "notes": "Vidéos tweets"},
        ]
    }


@app.get("/extract", response_model=ExtractResponse, tags=["Extraction"])
async def extract(url: str = Query(..., description="URL de la vidéo à extraire")):
    """
    Extrait les informations et URLs de téléchargement d'une vidéo.

    Supporte : TikTok (sans watermark), YouTube, Pinterest, Facebook, Instagram, LinkedIn, Twitter/X.
    """
    url = url.strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL invalide — doit commencer par http:// ou https://")

    start = time.monotonic()
    try:
        logger.info(f"Extraction → {url}")
        info = await extract_video_info(url)
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.info(f"Succès [{info.platform}] '{info.title[:60]}' — {elapsed}ms")
        return ExtractResponse(success=True, data=info, duration_ms=elapsed)

    except ValueError as e:
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.warning(f"Extraction échouée : {e}")
        return ExtractResponse(success=False, error=str(e), duration_ms=elapsed)

    except Exception as e:
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.error(f"Erreur interne : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne du serveur : {str(e)}")


@app.post("/extract/batch", response_model=BatchResponse, tags=["Extraction"])
async def extract_batch(body: BatchRequest):
    """
    Extrait plusieurs vidéos en parallèle (max 10 URLs).
    """
    tasks = [extract_video_info(url.strip()) for url in body.urls]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[ExtractResponse] = []
    succeeded = 0
    failed = 0

    for result in raw_results:
        if isinstance(result, Exception):
            results.append(ExtractResponse(success=False, error=str(result)))
            failed += 1
        else:
            results.append(ExtractResponse(success=True, data=result))
            succeeded += 1

    return BatchResponse(
        success=failed == 0,
        results=results,
        total=len(body.urls),
        succeeded=succeeded,
        failed=failed,
    )


@app.get("/detect", tags=["Utilitaires"])
async def detect(url: str = Query(..., description="URL à analyser")):
    """Détecte la plateforme d'une URL sans extraire la vidéo."""
    platform = detect_platform(url.strip())
    return {
        "url": url,
        "platform": platform,
        "supported": platform in SUPPORTED_PLATFORMS,
    }


# ─── Point d'entrée ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8032, reload=True, log_level="info")