"""
WaziScope - FastAPI Extractor Service v2.1
Fixes:
  - Pinterest: fallback scraper HTML quand yt-dlp échoue (API bloquée)
  - TikTok: headers CDN corrects pour le proxy
  - pin.it: résolution de redirection avant extraction
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import yt_dlp
import asyncio
import re
import time
import logging
import urllib.request
import urllib.parse
import json
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("waziscope")

executor = ThreadPoolExecutor(max_workers=4)

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="WaziScope Extractor",
    description="Extraire les URLs de vidéos depuis TikTok, Pinterest, Facebook, YouTube, LinkedIn",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    # Headers nécessaires pour télécharger cette vidéo (surtout TikTok)
    required_headers: dict = {}


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


# ─── Détection plateforme ─────────────────────────────────────────────────────

PLATFORM_PATTERNS: dict[str, str] = {
    "tiktok":    r"(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)",
    "youtube":   r"(youtube\.com|youtu\.be|youtube-nocookie\.com|music\.youtube\.com)",
    "pinterest": r"(pinterest\.(com|fr|ca|co\.\w+|at|de|es|pt|ru|ch|it|nz|au|co\.uk)|pin\.it)",
    "facebook":  r"(facebook\.com|fb\.com|fb\.watch|m\.facebook\.com)",
    "instagram": r"(instagram\.com|instagr\.am)",
    "linkedin":  r"(linkedin\.com|lnkd\.in)",
    "twitter":   r"(twitter\.com|t\.co|x\.com)",
}

SUPPORTED_PLATFORMS = set(PLATFORM_PATTERNS.keys())


def detect_platform(url: str) -> str:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return "unknown"


# ─── User-Agents ──────────────────────────────────────────────────────────────

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Mobile/15E148 Safari/604.1"
)
UA_ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.6367.82 Mobile Safari/537.36"
)


# ─── Headers par plateforme (pour le proxy de téléchargement) ─────────────────

DOWNLOAD_HEADERS: dict[str, dict] = {
    "tiktok": {
        "User-Agent": UA_ANDROID,
        "Referer": "https://www.tiktok.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
        "Range": "bytes=0-",
    },
    "youtube": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://www.youtube.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "pinterest": {
        "User-Agent": UA_MOBILE,
        "Referer": "https://www.pinterest.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "facebook": {
        "User-Agent": UA_ANDROID,
        "Referer": "https://www.facebook.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "instagram": {
        "User-Agent": UA_ANDROID,
        "Referer": "https://www.instagram.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "linkedin": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://www.linkedin.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "twitter": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://twitter.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
}


# ─── Options yt-dlp ──────────────────────────────────────────────────────────

def get_ydl_opts(platform: str) -> dict:
    base: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": UA_DESKTOP,
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "nocheckcertificate": False,
    }

    if platform == "tiktok":
        base.update({
            "format": "bestvideo+bestaudio/best",
            "extractor_args": {
                "tiktok": {
                    "webpage_download": ["1"],
                    "api_hostname": ["api22-normal-c-useast2a.tiktokv.com"],
                    "app_name": ["trill"],
                    "app_version": ["34.1.2"],
                    "manifest_app_version": ["341"],
                }
            },
            "http_headers": {
                **base["http_headers"],
                "User-Agent": UA_MOBILE,
                "Referer": "https://www.tiktok.com/",
            },
        })

    elif platform == "youtube":
        base.update({
            "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best",
            "merge_output_format": "mp4",
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
                "User-Agent": UA_MOBILE,
                "Referer": "https://www.pinterest.com/",
                "X-Pinterest-AppState": "active",
            },
        })

    elif platform == "facebook":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "User-Agent": UA_ANDROID,
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


# ─── Pinterest custom scraper (fallback quand yt-dlp échoue) ─────────────────

def _resolve_pin_it(url: str) -> str:
    """Résout une URL pin.it en URL pinterest.com complète."""
    if "pin.it" not in url:
        return url
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA_MOBILE},
            method="HEAD",
        )
        opener = urllib.request.build_opener(
            urllib.request.HTTPRedirectHandler()
        )
        # Suivre les redirections manuellement
        resp = opener.open(req, timeout=10)
        return resp.geturl()
    except Exception:
        try:
            # Fallback: GET request
            req = urllib.request.Request(url, headers={"User-Agent": UA_MOBILE})
            resp = urllib.request.urlopen(req, timeout=10)
            return resp.geturl()
        except Exception:
            return url


def _pinterest_scrape(url: str) -> Optional[VideoInfo]:
    """
    Scraper Pinterest HTML direct.
    Pinterest embarque les données de la pin dans __PWS_DATA__ ou
    window.__redux_data__ dans le HTML de la page.
    """
    # Résoudre pin.it d'abord
    resolved_url = _resolve_pin_it(url)
    logger.info(f"Pinterest scrape: {resolved_url}")

    headers = {
        "User-Agent": UA_MOBILE,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        req = urllib.request.Request(resolved_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            # Pinterest peut servir du gzip
            try:
                import gzip
                html = gzip.decompress(raw).decode("utf-8", errors="replace")
            except Exception:
                html = raw.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Pinterest HTTP error: {e}")
        return None

    # ── Chercher __PWS_DATA__ (format moderne Pinterest) ──────────────────
    pws_match = re.search(
        r'<script[^>]+id="__PWS_DATA__"[^>]*>\s*(\{.*?\})\s*</script>',
        html,
        re.DOTALL,
    )
    if pws_match:
        try:
            pws = json.loads(pws_match.group(1))
            return _parse_pinterest_pws(pws, resolved_url)
        except Exception as e:
            logger.debug(f"PWS parse error: {e}")

    # ── Chercher window.__redux_data__ (ancien format) ────────────────────
    redux_match = re.search(
        r'window\.__redux_data__\s*=\s*(\{.*?\});\s*(?:window|</script>)',
        html,
        re.DOTALL,
    )
    if redux_match:
        try:
            redux = json.loads(redux_match.group(1))
            return _parse_pinterest_redux(redux, resolved_url)
        except Exception as e:
            logger.debug(f"Redux parse error: {e}")

    # ── Chercher les URLs vidéo directement dans le HTML ──────────────────
    # Pinterest met les URLs m3u8 et mp4 dans le HTML en JSON
    video_urls = re.findall(r'"(?:url|V_720P|V_1080P|V_480P|V_240P)"\s*:\s*"(https://[^"]+(?:\.mp4|\.m3u8)[^"]*)"', html)
    if video_urls:
        best_url = video_urls[-1]
        title_match = re.search(r'"title"\s*:\s*"([^"]{3,200})"', html)
        thumb_match = re.search(r'"image_signature"\s*:\s*"([^"]+)"', html)
        title = title_match.group(1) if title_match else "Vidéo Pinterest"
        return VideoInfo(
            original_url=url,
            title=title,
            platform="pinterest",
            formats=[FormatInfo(format_id="0", ext="mp4", quality="best", url=best_url)],
            best_url=best_url,
            no_watermark_url=best_url,
            required_headers=DOWNLOAD_HEADERS["pinterest"],
        )

    logger.warning("Pinterest: aucune vidéo trouvée dans le HTML")
    return None


def _parse_pinterest_pws(data: dict, original_url: str) -> Optional[VideoInfo]:
    """Parse le bloc __PWS_DATA__ de Pinterest."""
    try:
        # Naviguer dans la structure Pinterest PWS
        props = data.get("props", {})
        page_props = props.get("pageProps", {})

        # Chercher dans initialReduxState ou les données de pin
        initial = page_props.get("initialReduxState", {})

        # Chercher le pin dans les ressources
        pins = (
            initial.get("pins", {})
            or initial.get("resources", {}).get("PinResource", {})
        )

        video_url = None
        title     = "Vidéo Pinterest"
        thumbnail = None

        for pin_id, pin_data in pins.items():
            if isinstance(pin_data, dict):
                # Chercher l'objet pin avec les données
                actual = pin_data.get("data", pin_data)

                # Chercher les vidéos
                videos = actual.get("videos", {}) or actual.get("story_pin_data", {})
                if videos:
                    video_list = videos.get("video_list", {})
                    for quality in ["V_1080P", "V_720P", "V_480P", "V_240P", "V_HLSV4_T1"]:
                        if quality in video_list:
                            video_url = video_list[quality].get("url")
                            if video_url:
                                break

                title     = actual.get("title") or actual.get("description") or "Vidéo Pinterest"
                thumbnail = actual.get("images", {}).get("orig", {}).get("url")

                if video_url:
                    break

        if not video_url:
            return None

        return VideoInfo(
            original_url=original_url,
            title=str(title)[:200],
            thumbnail=thumbnail,
            platform="pinterest",
            formats=[FormatInfo(format_id="0", ext="mp4", quality="best", url=video_url)],
            best_url=video_url,
            no_watermark_url=video_url,
            required_headers=DOWNLOAD_HEADERS["pinterest"],
        )

    except Exception as e:
        logger.debug(f"PWS parse exception: {e}")
        return None


def _parse_pinterest_redux(data: dict, original_url: str) -> Optional[VideoInfo]:
    """Parse le bloc __redux_data__ de Pinterest."""
    try:
        pins = data.get("pins", {})
        for pin_id, pin_data in pins.items():
            videos = pin_data.get("videos", {})
            if not videos:
                continue
            video_list = videos.get("video_list", {})
            video_url = None
            for quality in ["V_1080P", "V_720P", "V_480P", "V_240P"]:
                if quality in video_list:
                    video_url = video_list[quality].get("url")
                    if video_url:
                        break
            if video_url:
                title     = pin_data.get("title") or pin_data.get("description") or "Vidéo Pinterest"
                thumbnail = pin_data.get("images", {}).get("orig", {}).get("url")
                return VideoInfo(
                    original_url=original_url,
                    title=str(title)[:200],
                    thumbnail=thumbnail,
                    platform="pinterest",
                    formats=[FormatInfo(format_id="0", ext="mp4", quality="best", url=video_url)],
                    best_url=video_url,
                    no_watermark_url=video_url,
                    required_headers=DOWNLOAD_HEADERS["pinterest"],
                )
    except Exception as e:
        logger.debug(f"Redux parse exception: {e}")
    return None


# ─── Helpers de parsing formats yt-dlp ────────────────────────────────────────

def _is_no_watermark(fmt: dict, platform: str) -> bool:
    if platform != "tiktok":
        return False
    fmt_id   = (fmt.get("format_id") or "").lower()
    fmt_note = (fmt.get("format_note") or "").lower()
    fmt_url  = (fmt.get("url") or "").lower()
    no_wm    = ["no_watermark", "nowm", "non_watermark", "download", "play_addr"]
    bad_wm   = ["watermark", "wm_video"]
    for s in no_wm:
        if s in fmt_id or s in fmt_note or s in fmt_url:
            return True
    for s in bad_wm:
        if s in fmt_id or s in fmt_note:
            return False
    return False


def _parse_formats(
    info: dict, platform: str
) -> tuple[list[FormatInfo], str | None, str | None, str | None]:
    formats: list[FormatInfo] = []
    best_url = no_watermark_url = audio_only_url = None

    for fmt in info.get("formats") or []:
        raw_url = fmt.get("url") or fmt.get("manifest_url")
        if not raw_url:
            continue

        vcodec       = fmt.get("vcodec") or ""
        acodec       = fmt.get("acodec") or ""
        is_video     = vcodec not in ("none", "", None)
        is_audio_only = not is_video and acodec not in ("none", "", None)
        no_wm        = _is_no_watermark(fmt, platform)

        formats.append(FormatInfo(
            format_id=fmt.get("format_id") or "unknown",
            ext=fmt.get("ext") or "mp4",
            quality=fmt.get("format_note") or fmt.get("height") or "?",
            url=raw_url,
            filesize=fmt.get("filesize") or fmt.get("filesize_approx"),
            width=fmt.get("width"),
            height=fmt.get("height"),
            fps=fmt.get("fps"),
            vcodec=vcodec or None,
            acodec=acodec or None,
            no_watermark=no_wm,
        ))

        if is_audio_only and not audio_only_url:
            audio_only_url = raw_url
        if no_wm:
            no_watermark_url = raw_url

    video_fmts = [f for f in formats if f.vcodec and f.vcodec not in ("none", "")]
    best_url   = video_fmts[-1].url if video_fmts else (formats[-1].url if formats else None)

    if platform == "tiktok" and not no_watermark_url and best_url:
        no_watermark_url = best_url

    if not formats and "url" in info:
        u = info["url"]
        formats          = [FormatInfo(format_id="default", ext="mp4", quality="best", url=u)]
        best_url         = u
        no_watermark_url = u

    return formats, best_url, no_watermark_url, audio_only_url


# ─── Extraction principale ────────────────────────────────────────────────────

async def extract_video_info(url: str) -> VideoInfo:
    url      = url.strip()
    platform = detect_platform(url)

    if platform == "unknown":
        raise ValueError(
            f"Plateforme non reconnue. Supportées : {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )

    # ── Pinterest : essayer yt-dlp puis fallback scraper ──────────────────
    if platform == "pinterest":
        return await _extract_pinterest(url)

    # ── Autres plateformes : yt-dlp direct ───────────────────────────────
    ydl_opts = get_ydl_opts(platform)
    loop     = asyncio.get_event_loop()

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
            raise ValueError("Cette vidéo n'est pas disponible.")
        if "Sign in" in msg or "login" in msg.lower():
            raise ValueError("Cette vidéo nécessite une connexion.")
        if "removed" in msg.lower() or "deleted" in msg.lower():
            raise ValueError("Cette vidéo a été supprimée.")
        raise ValueError(f"Impossible d'extraire : {msg}")
    except Exception as e:
        raise ValueError(f"Erreur inattendue : {str(e)}")

    if not info:
        raise ValueError("Aucune information trouvée.")

    formats, best_url, no_watermark_url, audio_only_url = _parse_formats(info, platform)

    # Headers de téléchargement requis (surtout TikTok)
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


async def _extract_pinterest(url: str) -> VideoInfo:
    """
    Essaie yt-dlp en premier, puis le scraper HTML en fallback.
    """
    loop = asyncio.get_event_loop()

    # 1. Résoudre pin.it → pinterest.com
    if "pin.it" in url:
        resolved = await loop.run_in_executor(executor, _resolve_pin_it, url)
        logger.info(f"pin.it resolved: {url} → {resolved}")
        url = resolved

    # 2. Tenter yt-dlp
    ydl_opts = get_ydl_opts("pinterest")

    def _ytdlp_extract():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.debug(f"yt-dlp Pinterest failed: {e}")
            return None

    info = await loop.run_in_executor(executor, _ytdlp_extract)

    if info:
        formats, best_url, no_watermark_url, audio_only_url = _parse_formats(info, "pinterest")
        if best_url:
            return VideoInfo(
                original_url=url,
                title=info.get("title") or "Vidéo Pinterest",
                description=info.get("description"),
                author=info.get("uploader"),
                thumbnail=info.get("thumbnail"),
                duration=info.get("duration"),
                platform="pinterest",
                formats=formats,
                best_url=best_url,
                no_watermark_url=no_watermark_url,
                audio_only_url=audio_only_url,
                required_headers=DOWNLOAD_HEADERS["pinterest"],
            )

    # 3. Fallback scraper HTML
    logger.info("Pinterest: yt-dlp failed, trying HTML scraper...")
    result = await loop.run_in_executor(executor, _pinterest_scrape, url)

    if result:
        return result

    raise ValueError(
        "Impossible d'extraire cette vidéo Pinterest. "
        "Vérifiez que l'URL est une vidéo publique et non un lien raccourci invalide. "
        "Si l'erreur persiste, Pinterest a peut-être bloqué l'accès — essayez l'URL complète pinterest.com/pin/..."
    )


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Système"])
async def health():
    return {
        "status": "ok",
        "service": "waziscope-extractor",
        "version": "2.1.0",
        "yt_dlp_version": yt_dlp.version.__version__,
    }


@app.get("/platforms", tags=["Système"])
async def get_platforms():
    return {
        "platforms": [
            {"id": "tiktok",    "name": "TikTok",    "no_watermark": True,  "notes": "Sans watermark via API mobile"},
            {"id": "youtube",   "name": "YouTube",   "no_watermark": False, "notes": "HD jusqu'à 1080p"},
            {"id": "pinterest", "name": "Pinterest", "no_watermark": False, "notes": "MP4 direct (scraper intégré)"},
            {"id": "facebook",  "name": "Facebook",  "no_watermark": False, "notes": "Vidéos publiques"},
            {"id": "instagram", "name": "Instagram", "no_watermark": False, "notes": "Reels & posts publics"},
            {"id": "linkedin",  "name": "LinkedIn",  "no_watermark": False, "notes": "Vidéos natives"},
            {"id": "twitter",   "name": "Twitter/X", "no_watermark": False, "notes": "Vidéos tweets"},
        ]
    }


@app.get("/extract", response_model=ExtractResponse, tags=["Extraction"])
async def extract(url: str = Query(..., description="URL de la vidéo")):
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL invalide")

    start = time.monotonic()
    try:
        logger.info(f"Extraction → {url}")
        info    = await extract_video_info(url)
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.info(f"OK [{info.platform}] '{info.title[:60]}' — {elapsed}ms")
        return ExtractResponse(success=True, data=info, duration_ms=elapsed)
    except ValueError as e:
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.warning(f"Extraction échouée : {e}")
        return ExtractResponse(success=False, error=str(e), duration_ms=elapsed)
    except Exception as e:
        logger.error(f"Erreur interne : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/batch", response_model=BatchResponse, tags=["Extraction"])
async def extract_batch(body: BatchRequest):
    tasks      = [extract_video_info(url.strip()) for url in body.urls]
    raw        = await asyncio.gather(*tasks, return_exceptions=True)
    results    = []
    succeeded  = failed = 0
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


@app.get("/detect", tags=["Utilitaires"])
async def detect(url: str = Query(...)):
    p = detect_platform(url.strip())
    return {"url": url, "platform": p, "supported": p in SUPPORTED_PLATFORMS}


@app.get("/headers/{platform}", tags=["Utilitaires"])
async def get_download_headers(platform: str):
    """Retourne les headers nécessaires pour télécharger depuis cette plateforme."""
    headers = DOWNLOAD_HEADERS.get(platform, {})
    return {"platform": platform, "headers": headers}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8032, reload=True, log_level="info")