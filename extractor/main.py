"""
WaziScope - FastAPI Extractor Service
Extracts direct video URLs from TikTok, Pinterest, Facebook
Uses yt-dlp under the hood
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import asyncio
import re
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WaziScope Extractor",
    description="Extract video URLs from TikTok, Pinterest, Facebook",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En prod, restreindre à ton domaine Laravel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Schémas ───────────────────────────────────────────────────────────────────

class VideoInfo(BaseModel):
    url: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    platform: str
    formats: list[dict] = []
    best_url: Optional[str] = None
    no_watermark_url: Optional[str] = None

class ExtractResponse(BaseModel):
    success: bool
    data: Optional[VideoInfo] = None
    error: Optional[str] = None


# ─── Détection plateforme ──────────────────────────────────────────────────────

def detect_platform(url: str) -> str:
    patterns = {
        "tiktok":    r"(tiktok\.com|vm\.tiktok\.com)",
        "pinterest": r"(pinterest\.(com|fr|ca|co\.\w+)|pin\.it)",
        "facebook":  r"(facebook\.com|fb\.com|fb\.watch)",
        "instagram": r"(instagram\.com|instagr\.am)",
    }
    for platform, pattern in patterns.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return "unknown"


# ─── Options yt-dlp par plateforme ────────────────────────────────────────────

def get_ydl_opts(platform: str) -> dict:
    base = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 30,
    }

    if platform == "tiktok":
        base.update({
            # Priorité aux formats sans watermark
            "format": "bestvideo[vcodec!=h265]+bestaudio/best",
            "extractor_args": {
                "tiktok": {"webpage_download": ["1"]}
            },
        })
    elif platform == "pinterest":
        base.update({
            "format": "best[ext=mp4]/best",
        })
    elif platform == "facebook":
        base.update({
            "format": "best[ext=mp4]/best",
        })
    else:
        base.update({"format": "best[ext=mp4]/best"})

    return base


# ─── Extraction ───────────────────────────────────────────────────────────────

async def extract_video_info(url: str) -> VideoInfo:
    platform = detect_platform(url)
    if platform == "unknown":
        raise ValueError(f"Plateforme non supportée pour l'URL: {url}")

    ydl_opts = get_ydl_opts(platform)

    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info

    try:
        info = await loop.run_in_executor(None, _extract)
    except yt_dlp.utils.DownloadError as e:
        raise ValueError(f"Impossible d'extraire: {str(e)}")

    # Récupérer les formats disponibles
    formats = []
    best_url = None
    no_watermark_url = None

    if "formats" in info:
        for fmt in info["formats"]:
            if fmt.get("url"):
                entry = {
                    "format_id": fmt.get("format_id", ""),
                    "ext":        fmt.get("ext", "mp4"),
                    "quality":    fmt.get("format_note", fmt.get("height", "?")),
                    "url":        fmt["url"],
                    "filesize":   fmt.get("filesize"),
                    "vcodec":     fmt.get("vcodec", ""),
                    "acodec":     fmt.get("acodec", ""),
                }
                formats.append(entry)

                # Détecter URL sans watermark pour TikTok
                if platform == "tiktok":
                    if "no_watermark" in fmt.get("format_id", "").lower() or \
                       "nowm" in fmt.get("url", "").lower():
                        no_watermark_url = fmt["url"]

        # Meilleure URL = dernier format (yt-dlp les trie par qualité croissante)
        if formats:
            best_url = formats[-1]["url"]
            if not no_watermark_url:
                no_watermark_url = best_url

    elif "url" in info:
        best_url = info["url"]
        no_watermark_url = info["url"]
        formats = [{"format_id": "default", "ext": "mp4", "url": best_url}]

    return VideoInfo(
        url=url,
        title=info.get("title", "Vidéo sans titre"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        platform=platform,
        formats=formats,
        best_url=best_url,
        no_watermark_url=no_watermark_url,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "waziscope-extractor"}


@app.get("/extract", response_model=ExtractResponse)
async def extract(url: str = Query(..., description="URL de la vidéo à extraire")):
    """
    Extrait les informations et URLs de téléchargement d'une vidéo.
    Supporte TikTok, Pinterest, Facebook.
    """
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL invalide")

    try:
        logger.info(f"Extraction de: {url}")
        info = await extract_video_info(url)
        return ExtractResponse(success=True, data=info)
    except ValueError as e:
        logger.warning(f"Erreur d'extraction: {e}")
        return ExtractResponse(success=False, error=str(e))
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@app.get("/platforms")
async def platforms():
    """Retourne les plateformes supportées."""
    return {
        "platforms": [
            {"id": "tiktok",    "name": "TikTok",     "icon": "🎵", "no_watermark": True},
            {"id": "pinterest", "name": "Pinterest",  "icon": "📌", "no_watermark": False},
            {"id": "facebook",  "name": "Facebook",   "icon": "📘", "no_watermark": False},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8032, reload=True)