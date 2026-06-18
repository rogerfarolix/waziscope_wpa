"""
WaziScope - FastAPI Extractor Service v3.0
Nouvelles fonctionnalités:
  - Plateformes étendues: Dailymotion, Vimeo, Twitch, Reddit, Rumble, Snapchat, Odysee
  - Support playlists YouTube (et autres)
  - Téléchargement longs métrages (pas de limite de durée)
  - Sélection de qualité par requête
  - Streaming SSE de progression via /extract/progress
  - Meilleure détection TikTok, Pinterest, Facebook
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
import yt_dlp
import asyncio
import re
import time
import logging
import urllib.request
import urllib.parse
import json
import gzip
import uuid
import httpx
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("waziscope")

executor = ThreadPoolExecutor(max_workers=6)

# Stockage en mémoire des progressions (jobId → état)
_progress_store: dict[str, dict] = {}

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="WaziScope Extractor",
    description="Extraire les URLs de vidéos depuis TikTok, YouTube, Pinterest, Facebook, Instagram, LinkedIn, Twitter, Dailymotion, Vimeo, Twitch, Reddit, Rumble, Odysee…",
    version="3.0.0",
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
    required_headers: dict = {}
    is_playlist: bool = False
    playlist_count: Optional[int] = None


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


class PlaylistRequest(BaseModel):
    url: str
    limit: int = 20

    @field_validator("limit")
    @classmethod
    def cap_limit(cls, v):
        return min(max(v, 1), 50)


class PlaylistItem(BaseModel):
    index: int
    success: bool
    data: Optional[VideoInfo] = None
    error: Optional[str] = None


class PlaylistResponse(BaseModel):
    success: bool
    playlist_title: Optional[str] = None
    total: int
    items: list[PlaylistItem] = []


# ─── Détection plateforme ─────────────────────────────────────────────────────

PLATFORM_PATTERNS: dict[str, str] = {
    "tiktok":      r"(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)",
    "youtube":     r"(youtube\.com|youtu\.be|youtube-nocookie\.com|music\.youtube\.com)",
    "pinterest":   r"(pinterest\.(com|fr|ca|co\.\w+|at|de|es|pt|ru|ch|it|nz|au|co\.uk)|pin\.it)",
    "facebook":    r"(facebook\.com|fb\.com|fb\.watch|m\.facebook\.com)",
    "instagram":   r"(instagram\.com|instagr\.am)",
    "linkedin":    r"(linkedin\.com|lnkd\.in)",
    "twitter":     r"(twitter\.com|t\.co|x\.com)",
    "dailymotion": r"(dailymotion\.com|dai\.ly)",
    "vimeo":       r"(vimeo\.com|player\.vimeo\.com)",
    "twitch":      r"(twitch\.tv|clips\.twitch\.tv)",
    "reddit":      r"(reddit\.com|redd\.it|v\.redd\.it|packaged-media\.redd\.it)",
    "rumble":      r"(rumble\.com)",
    "odysee":      r"(odysee\.com|lbry\.tv)",
    "snapchat":    r"(snapchat\.com|t\.snapchat\.com)",
    "bilibili":    r"(bilibili\.com|b23\.tv)",
    "weibo":       r"(weibo\.com|weibo\.cn)",
}

SUPPORTED_PLATFORMS = set(PLATFORM_PATTERNS.keys())

# Plateformes supportant les playlists
PLAYLIST_PLATFORMS = {"youtube", "dailymotion", "vimeo", "twitch", "rumble", "odysee", "bilibili"}


def detect_platform(url: str) -> str:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return "unknown"


# ─── User-Agents ──────────────────────────────────────────────────────────────

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.5 Mobile/15E148 Safari/604.1"
)
UA_ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.6478.72 Mobile Safari/537.36"
)


# ─── Headers par plateforme ───────────────────────────────────────────────────

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
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
    },
    "instagram": {
        "User-Agent": UA_ANDROID,
        "Referer": "https://www.instagram.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
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
    "dailymotion": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://www.dailymotion.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "vimeo": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://vimeo.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "twitch": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://www.twitch.tv/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "reddit": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://www.reddit.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "rumble": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://rumble.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "odysee": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://odysee.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "snapchat": {
        "User-Agent": UA_MOBILE,
        "Referer": "https://www.snapchat.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
    "bilibili": {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://www.bilibili.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    },
}


# ─── Options yt-dlp ──────────────────────────────────────────────────────────

def get_ydl_opts(platform: str, quality: str = "best") -> dict:
    # Qualité YouTube par défaut: 1080p
    yt_format = {
        "4k":   "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best",
        "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
        "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
        "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
        "audio": "bestaudio[ext=m4a]/bestaudio",
        "best": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best",
    }.get(quality, "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best")

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
                    "webpage_download": ["0"],
                    "api_hostname": ["api16-normal-c-alisg.tiktokv.com"],
                    "app_name": ["tiktok"],
                    "app_version": ["35.1.2"],
                    "manifest_app_version": ["351"],
                }
            },
            "http_headers": {
                **base["http_headers"],
                "User-Agent": UA_ANDROID,
                "Referer": "https://www.tiktok.com/",
            },
        })

    elif platform == "youtube":
        base.update({
            "format": yt_format,
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
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
            },
        })

    elif platform == "instagram":
        base.update({
            "format": "best[ext=mp4]/best",
            "http_headers": {
                **base["http_headers"],
                "User-Agent": UA_ANDROID,
                "Referer": "https://www.instagram.com/",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
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

    elif platform == "dailymotion":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.dailymotion.com/",
            },
        })

    elif platform == "vimeo":
        base.update({
            "format": yt_format,
            "merge_output_format": "mp4",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://vimeo.com/",
            },
        })

    elif platform == "twitch":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.twitch.tv/",
            },
        })

    elif platform == "reddit":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.reddit.com/",
            },
        })

    elif platform == "rumble":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://rumble.com/",
            },
        })

    elif platform == "odysee":
        base.update({
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://odysee.com/",
            },
        })

    elif platform == "snapchat":
        base.update({
            "format": "best[ext=mp4]/best",
            "http_headers": {
                **base["http_headers"],
                "User-Agent": UA_MOBILE,
                "Referer": "https://www.snapchat.com/",
            },
        })

    elif platform == "bilibili":
        base.update({
            "format": "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
            "http_headers": {
                **base["http_headers"],
                "Referer": "https://www.bilibili.com/",
            },
        })

    else:
        base.update({"format": "best[ext=mp4]/bestvideo+bestaudio/best"})

    return base


# ─── Helpers HTTP communs ─────────────────────────────────────────────────────

def _http_get_html(url: str, headers: dict, timeout: int = 20) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return gzip.decompress(raw).decode("utf-8", errors="replace")
            except Exception:
                return raw.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"HTTP GET error [{url[:60]}]: {e}")
        return None


def _resolve_redirect(url: str, ua: str = UA_ANDROID) -> str:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": ua, "Accept": "text/html,*/*"},
        )
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        resp = opener.open(req, timeout=10)
        return resp.geturl()
    except Exception:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            resp = urllib.request.urlopen(req, timeout=10)
            return resp.geturl()
        except Exception:
            return url


# ─── Facebook scraper ─────────────────────────────────────────────────────────

def _resolve_facebook_url(url: str) -> str:
    needs_resolve = (
        re.search(r'facebook\.com/share/', url, re.I) or
        re.search(r'fb\.watch/', url, re.I) or
        re.search(r'^https?://fb\.com/', url, re.I)
    )
    if not needs_resolve:
        return url

    resolved = _resolve_redirect(url, UA_ANDROID)
    if resolved != url:
        logger.info(f"Facebook URL resolved: {url[:80]} → {resolved[:80]}")
    return resolved


def _facebook_scrape(url: str) -> Optional[VideoInfo]:
    headers = {
        "User-Agent": UA_ANDROID,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }

    html = _http_get_html(url, headers)
    if not html:
        return None

    html = html.replace('\\u0026', '&').replace('\\u003C', '<').replace('\\u003E', '>')

    video_patterns = [
        r'"playable_url_quality_hd"\s*:\s*"(https?://[^"\\]+(?:\\.[^"\\]*)*)"',
        r'"browser_native_hd_url"\s*:\s*"(https?://[^"\\]+(?:\\.[^"\\]*)*)"',
        r'"hd_src"\s*:\s*"(https?://[^"\\]+(?:\\.[^"\\]*)*)"',
        r'"playable_url"\s*:\s*"(https?://[^"\\]+(?:\\.[^"\\]*)*)"',
        r'"browser_native_sd_url"\s*:\s*"(https?://[^"\\]+(?:\\.[^"\\]*)*)"',
        r'"sd_src"\s*:\s*"(https?://[^"\\]+(?:\\.[^"\\]*)*)"',
        r'"video_url"\s*:\s*"(https?://[^"\\]+(?:\\.[^"\\]*)*\.mp4[^"\\]*)"',
    ]

    video_url = None
    for pattern in video_patterns:
        m = re.search(pattern, html)
        if m:
            candidate = m.group(1).replace('\\/', '/').replace('\\/','/')
            if candidate.startswith('http'):
                video_url = candidate
                break

    if not video_url:
        return None

    title = "Vidéo Facebook"
    for tp in [
        r'"title"\s*:\s*\{"text"\s*:\s*"([^"]{3,200})"',
        r'<title[^>]*>([^<]{3,200})</title>',
        r'property="og:title"\s+content="([^"]{3,200})"',
    ]:
        m = re.search(tp, html)
        if m:
            t = m.group(1).strip()
            if t and t.lower() not in ("facebook", ""):
                title = t
                break

    thumbnail = None
    for tp in [
        r'"thumbnailImage"\s*:\s*\{"uri"\s*:\s*"([^"]+)"',
        r'property="og:image"\s+content="([^"]+)"',
    ]:
        m = re.search(tp, html)
        if m:
            thumbnail = m.group(1).replace('\\/', '/')
            break

    return VideoInfo(
        original_url=url,
        title=title[:200],
        thumbnail=thumbnail,
        platform="facebook",
        formats=[FormatInfo(format_id="0", ext="mp4", quality="best", url=video_url)],
        best_url=video_url,
        no_watermark_url=video_url,
        required_headers=DOWNLOAD_HEADERS["facebook"],
    )


async def _extract_facebook(url: str) -> VideoInfo:
    loop = asyncio.get_event_loop()

    url = await loop.run_in_executor(executor, _resolve_facebook_url, url)

    ydl_opts = get_ydl_opts("facebook")

    def _ytdlp_extract():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.debug(f"yt-dlp Facebook failed: {e}")
            return None

    info = await loop.run_in_executor(executor, _ytdlp_extract)

    if info:
        formats, best_url, no_watermark_url, audio_only_url = _parse_formats(info, "facebook")
        if best_url:
            return VideoInfo(
                original_url=url,
                title=info.get("title") or "Vidéo Facebook",
                description=info.get("description"),
                author=info.get("uploader"),
                thumbnail=info.get("thumbnail"),
                duration=info.get("duration"),
                view_count=info.get("view_count"),
                like_count=info.get("like_count"),
                platform="facebook",
                formats=formats,
                best_url=best_url,
                no_watermark_url=no_watermark_url,
                audio_only_url=audio_only_url,
                required_headers=DOWNLOAD_HEADERS["facebook"],
            )

    logger.info("Facebook: yt-dlp failed, trying HTML scraper...")
    result = await loop.run_in_executor(executor, _facebook_scrape, url)

    if result:
        return result

    raise ValueError(
        "Impossible d'extraire cette vidéo Facebook. "
        "Assurez-vous que la vidéo est publique."
    )


# ─── Pinterest scraper ────────────────────────────────────────────────────────

def _resolve_pin_it(url: str) -> str:
    """Résout pin.it et nettoie l'URL finale (supprime /sent/, invite_code, etc.)."""
    if "pin.it" in url:
        resolved = _resolve_redirect(url, UA_MOBILE)
        logger.info(f"pin.it resolved: {url} → {resolved[:80]}")
        url = resolved

    # Normalise : extrait juste /pin/<id>/ sans le reste
    m = re.search(r'(https?://(?:www\.)?pinterest\.com/pin/\d+)', url)
    if m:
        return m.group(1) + "/"
    return url


def _pinterest_scrape(url: str) -> Optional[VideoInfo]:
    resolved_url = _resolve_pin_it(url)

    headers = {
        "User-Agent": UA_MOBILE,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Accept-Encoding": "gzip, deflate",
    }

    html = _http_get_html(resolved_url, headers)
    if not html:
        return None

    pws_match = re.search(
        r'<script[^>]+id="__PWS_DATA__"[^>]*>\s*(\{.*?\})\s*</script>',
        html, re.DOTALL,
    )
    if pws_match:
        try:
            pws = json.loads(pws_match.group(1))
            result = _parse_pinterest_pws(pws, resolved_url)
            if result:
                return result
        except Exception as e:
            logger.debug(f"PWS parse error: {e}")

    redux_match = re.search(
        r'window\.__redux_data__\s*=\s*(\{.*?\});\s*(?:window|</script>)',
        html, re.DOTALL,
    )
    if redux_match:
        try:
            redux = json.loads(redux_match.group(1))
            result = _parse_pinterest_redux(redux, resolved_url)
            if result:
                return result
        except Exception as e:
            logger.debug(f"Redux parse error: {e}")

    # Fallback : regex directe sur les URLs pinimg.com/v.pinimg.com
    video_urls = re.findall(
        r'"(?:url|V_1080P|V_720P|V_480P|V_240P)"\s*:\s*"(https://[^"]+(?:\.mp4|\.m3u8)[^"]*)"',
        html
    )
    # Aussi chercher toute URL pinimg vidéo
    pinimg_urls = re.findall(
        r'(https://v(?:\d+)?\.pinimg\.com/videos/[^"\'>\s]+\.mp4[^"\'>\s]*)',
        html
    )
    all_video_urls = video_urls + pinimg_urls
    if all_video_urls:
        # Préférer les MP4 aux HLS, convertir si nécessaire
        mp4_urls = [u for u in all_video_urls if u.endswith(".mp4")]
        best_url = _pinimg_hls_to_mp4(mp4_urls[-1] if mp4_urls else all_video_urls[-1])
        title = _extract_pinterest_title(html) or "Vidéo Pinterest"
        thumb_m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        thumbnail = thumb_m.group(1) if thumb_m else None
        ext = "mp4" if best_url and best_url.endswith(".mp4") else "m3u8"
        return VideoInfo(
            original_url=resolved_url,
            title=title,
            thumbnail=thumbnail,
            platform="pinterest",
            formats=[FormatInfo(format_id="0", ext=ext, quality="best", url=best_url)],
            best_url=best_url,
            no_watermark_url=best_url,
            required_headers=DOWNLOAD_HEADERS["pinterest"],
        )

    return None


def _extract_pinterest_title(html: str) -> Optional[str]:
    """Extrait le titre d'une page Pinterest — ignore les titres parasites courts."""
    patterns = [
        r'property="og:title"\s+content="([^"]{4,200})"',
        r'"seo_title"\s*:\s*"([^"]{4,200})"',
        r'"title"\s*:\s*"([^"]{4,200})"(?!\s*:)',  # exclut les clés imbriquées
        r'<title[^>]*>([^<]{4,200})</title>',
    ]
    stopwords = {"pinterest", "pin", ".", "", "video", "vidéo"}
    for p in patterns:
        for m in re.finditer(p, html, re.IGNORECASE):
            t = m.group(1).strip()
            t = re.sub(r'\s*[|\-–]\s*Pinterest.*$', '', t, flags=re.IGNORECASE).strip()
            if t and t.lower() not in stopwords and len(t) > 3:
                return t
    return None


def _parse_pinterest_pws(data: dict, original_url: str) -> Optional[VideoInfo]:
    try:
        props = data.get("props", {})
        page_props = props.get("pageProps", {})
        initial = page_props.get("initialReduxState", {})
        pins = (
            initial.get("pins", {})
            or initial.get("resources", {}).get("PinResource", {})
        )
        video_url = None
        title = "Vidéo Pinterest"
        thumbnail = None

        for _, pin_data in pins.items():
            if isinstance(pin_data, dict):
                actual = pin_data.get("data", pin_data)
                videos = actual.get("videos", {}) or actual.get("story_pin_data", {})
                if videos:
                    video_list = videos.get("video_list", {})
                    for quality in ["V_1080P", "V_720P", "V_480P", "V_240P", "V_HLSV4_T1"]:
                        if quality in video_list:
                            video_url = video_list[quality].get("url")
                            if video_url:
                                break
                title = actual.get("title") or actual.get("description") or "Vidéo Pinterest"
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
    try:
        pins = data.get("pins", {})
        for _, pin_data in pins.items():
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
                title = pin_data.get("title") or pin_data.get("description") or "Vidéo Pinterest"
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


def _pinimg_hls_to_mp4(url: Optional[str]) -> Optional[str]:
    """Convertit une URL HLS pinimg.com en MP4 direct (même contenu, format différent)."""
    if not url:
        return url
    # https://v1.pinimg.com/videos/iht/hls/v2/.../file_720w.m3u8
    # → https://v1.pinimg.com/videos/iht/expMp4/v2/.../file_720w.mp4
    if "pinimg.com" in url and "/hls/" in url and url.endswith(".m3u8"):
        return url.replace("/hls/", "/expMp4/").replace(".m3u8", ".mp4")
    return url


async def _extract_pinterest(url: str) -> VideoInfo:
    loop = asyncio.get_event_loop()

    if "pin.it" in url:
        url = await loop.run_in_executor(executor, _resolve_pin_it, url)

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
            raw_title = info.get("title") or ""
            good_title = raw_title.strip() if len(raw_title.strip()) > 3 else None

            # Convertir HLS pinimg → MP4 direct (même CDN, chemin différent)
            best_url         = _pinimg_hls_to_mp4(best_url)
            no_watermark_url = _pinimg_hls_to_mp4(no_watermark_url or best_url)

            # Si le titre est toujours générique, tenter l'HTML en parallèle
            if not good_title:
                scrape_result = await loop.run_in_executor(executor, _pinterest_scrape, url)
                if scrape_result and scrape_result.title and len(scrape_result.title) > 3:
                    good_title = scrape_result.title

            return VideoInfo(
                original_url=url,
                title=good_title or "Vidéo Pinterest",
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

    logger.info("Pinterest: yt-dlp failed, trying HTML scraper...")
    result = await loop.run_in_executor(executor, _pinterest_scrape, url)

    if result:
        return result

    raise ValueError(
        "Impossible d'extraire cette vidéo Pinterest. "
        "Vérifiez que l'URL est une vidéo publique."
    )


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

    if not no_watermark_url and best_url:
        no_watermark_url = best_url

    if not formats and "url" in info:
        u = info["url"]
        formats          = [FormatInfo(format_id="default", ext="mp4", quality="best", url=u)]
        best_url         = u
        no_watermark_url = u

    return formats, best_url, no_watermark_url, audio_only_url


# ─── TikTok : retry multi-région ─────────────────────────────────────────────

# Endpoints classés par proximité : Singapore/EU d'abord, US en fallback
_TIKTOK_API_HOSTS = [
    ("api16-normal-c-alisg.tiktokv.com",  "tiktok",   "35.1.2",  "351"),
    ("api19-normal-c-alisg.tiktokv.com",  "tiktok",   "35.1.2",  "351"),
    ("api21-normal-c-alisg.tiktokv.com",  "tiktok",   "35.1.2",  "351"),
    ("api31-normal-c-alisg.tiktokv.com",  "trill",    "34.1.2",  "341"),
    ("api16-normal-c-useast1a.tiktokv.com","trill",   "34.1.2",  "341"),
    ("api22-normal-c-useast2a.tiktokv.com","trill",   "34.1.2",  "341"),
    ("api19-normal-c-useast2a.tiktokv.com","tiktok",  "35.1.2",  "351"),
    ("api16-normal-c-maliva.tiktokv.com",  "tiktok",  "35.1.2",  "351"),
]


def _make_tiktok_opts(hostname: str, app_name: str, app_version: str, manifest: str) -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "nocheckcertificate": True,
        "format": "bestvideo+bestaudio/best",
        "extractor_args": {
            "tiktok": {
                "webpage_download": ["0"],
                "api_hostname": [hostname],
                "app_name": [app_name],
                "app_version": [app_version],
                "manifest_app_version": [manifest],
            }
        },
        "http_headers": {
            "User-Agent": UA_ANDROID,
            "Referer": "https://www.tiktok.com/",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


async def _extract_tiktok(url: str) -> VideoInfo:
    loop = asyncio.get_event_loop()
    last_err = "Échec TikTok"

    # ── 1. Essai yt-dlp multi-endpoints ──────────────────────────────────────
    for hostname, app_name, app_version, manifest in _TIKTOK_API_HOSTS:
        opts = _make_tiktok_opts(hostname, app_name, app_version, manifest)

        def _try(o=opts):
            with yt_dlp.YoutubeDL(o) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await loop.run_in_executor(executor, _try)
            if not info:
                continue

            formats, best_url, no_watermark_url, audio_only_url = _parse_formats(info, "tiktok")
            logger.info(f"TikTok OK via {hostname}")
            return VideoInfo(
                original_url=url,
                title=info.get("title") or "Vidéo TikTok",
                author=info.get("uploader") or info.get("creator"),
                thumbnail=info.get("thumbnail"),
                duration=info.get("duration"),
                view_count=info.get("view_count"),
                like_count=info.get("like_count"),
                platform="tiktok",
                formats=formats,
                best_url=best_url,
                no_watermark_url=no_watermark_url,
                audio_only_url=audio_only_url,
                required_headers=DOWNLOAD_HEADERS.get("tiktok", {}),
            )
        except Exception as e:
            last_err = str(e)
            logger.debug(f"TikTok {hostname} failed: {last_err[:120]}")
            continue

    # ── 2. Fallback tikwm.com (API tierce, fiable, gratuite) ─────────────────
    logger.info("TikTok: yt-dlp bloqué, fallback tikwm.com...")
    try:
        result = await loop.run_in_executor(executor, _tikwm_extract, url)
        if result:
            logger.info("TikTok OK via tikwm.com")
            return result
    except Exception as e:
        logger.debug(f"tikwm failed: {e}")

    raise ValueError(
        "Impossible d'extraire cette vidéo TikTok. "
        "Vérifiez que la vidéo est publique et réessayez."
    )


def _tikwm_extract(url: str) -> Optional[VideoInfo]:
    """Fallback TikTok via tikwm.com API (fonctionne quand l'IP serveur est bloquée par TikTok)."""
    import urllib.request, urllib.parse, json as _json

    api_url = "https://www.tikwm.com/api/"
    data    = urllib.parse.urlencode({"url": url, "count": 12, "cursor": 0, "hd": 1}).encode()
    req     = urllib.request.Request(
        api_url, data=data, method="POST",
        headers={
            "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer":      "https://www.tikwm.com/",
            "Origin":       "https://www.tikwm.com",
            "Accept":       "application/json, text/plain, */*",
        },
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = _json.loads(resp.read().decode())

    if payload.get("code") != 0:
        logger.debug(f"tikwm non-zero code: {payload.get('msg')}")
        return None

    d = payload.get("data", {})
    if not d:
        return None

    # Préférer play (sans WM) ; wmplay en fallback
    no_wm_url = d.get("hdplay") or d.get("play")
    wm_url    = d.get("wmplay") or no_wm_url
    audio_url = d.get("music")
    thumb     = d.get("cover") or d.get("origin_cover")
    title     = d.get("title") or "Vidéo TikTok"
    author    = (d.get("author") or {}).get("nickname") or d.get("author_unique_id")
    duration  = d.get("duration")

    if not no_wm_url:
        return None

    fmts = [FormatInfo(format_id="nowm", ext="mp4", quality="best",
                       url=no_wm_url, no_watermark=True)]
    if wm_url and wm_url != no_wm_url:
        fmts.append(FormatInfo(format_id="wm", ext="mp4", quality="wm",
                               url=wm_url, no_watermark=False))

    return VideoInfo(
        original_url=url,
        title=title[:200],
        author=author,
        thumbnail=thumb,
        duration=duration,
        platform="tiktok",
        formats=fmts,
        best_url=no_wm_url,
        no_watermark_url=no_wm_url,
        audio_only_url=audio_url,
        required_headers={
            "User-Agent": UA_ANDROID,
            "Referer":    "https://www.tiktok.com/",
        },
    )


# ─── Dailymotion : API metadata (pas d'impersonation) ────────────────────────

def _dailymotion_api(url: str) -> Optional[VideoInfo]:
    """Utilise l'API metadata Dailymotion — ne nécessite pas d'impersonation navigateur."""
    m = re.search(r'dailymotion\.com/(?:video|embed/video)/([a-zA-Z0-9]+)', url)
    if not m:
        m = re.search(r'dai\.ly/([a-zA-Z0-9]+)', url)
    if not m:
        return None
    vid_id = m.group(1)

    api_url = (
        f"https://www.dailymotion.com/player/metadata/video/{vid_id}"
        "?embedder=https://www.dailymotion.com&locale=fr_FR&dmV1st=&dmTs=0&is_native_app=0"
    )
    headers = {
        "User-Agent": UA_DESKTOP,
        "Referer": "https://www.dailymotion.com/",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.dailymotion.com",
    }
    try:
        html = _http_get_html(api_url, headers)
        if not html:
            return None
        data = json.loads(html)
    except Exception as e:
        logger.debug(f"Dailymotion API parse error: {e}")
        return None

    qualities = data.get("qualities", {})
    fmts: list[FormatInfo] = []
    best_url = None

    for q_name in ["1080", "720", "480", "380", "240", "auto"]:
        streams = qualities.get(q_name, [])
        for s in (streams if isinstance(streams, list) else []):
            stream_url = s.get("url")
            if stream_url and "m3u8" not in stream_url:
                fmts.append(FormatInfo(
                    format_id=q_name, ext="mp4", quality=f"{q_name}p",
                    url=stream_url, no_watermark=False,
                ))
                if not best_url:
                    best_url = stream_url

    # Fallback HLS si pas de MP4
    if not best_url:
        for q_name in ["auto", "1080", "720"]:
            for s in (qualities.get(q_name) or []):
                u = s.get("url", "")
                if u:
                    fmts.append(FormatInfo(format_id=q_name, ext="m3u8", quality=q_name, url=u))
                    best_url = best_url or u
                    break

    if not best_url:
        return None

    title     = data.get("title") or "Vidéo Dailymotion"
    thumbnail = data.get("poster_url") or (data.get("thumbnails") or {}).get("x240")
    duration  = data.get("duration")

    return VideoInfo(
        original_url=url,
        title=title[:200],
        thumbnail=thumbnail,
        duration=duration,
        platform="dailymotion",
        formats=fmts if fmts else [FormatInfo(format_id="0", ext="mp4", quality="best", url=best_url)],
        best_url=best_url,
        no_watermark_url=best_url,
        required_headers=DOWNLOAD_HEADERS.get("dailymotion", {}),
    )


async def _extract_dailymotion(url: str) -> VideoInfo:
    loop = asyncio.get_event_loop()
    # Essai yt-dlp sans impersonation
    opts = {**get_ydl_opts("dailymotion"), "impersonate": None, "nocheckcertificate": True}
    def _try():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    try:
        info = await loop.run_in_executor(executor, _try)
        if info:
            formats, best_url, no_wm_url, audio_url = _parse_formats(info, "dailymotion")
            if best_url:
                return VideoInfo(
                    original_url=url, title=info.get("title") or "Vidéo Dailymotion",
                    author=info.get("uploader"), thumbnail=info.get("thumbnail"),
                    duration=info.get("duration"), view_count=info.get("view_count"),
                    platform="dailymotion", formats=formats,
                    best_url=best_url, no_watermark_url=no_wm_url or best_url,
                    audio_only_url=audio_url,
                    required_headers=DOWNLOAD_HEADERS.get("dailymotion", {}),
                )
    except Exception as e:
        logger.debug(f"Dailymotion yt-dlp failed: {e}")

    logger.info("Dailymotion: yt-dlp failed, fallback API metadata...")
    result = await loop.run_in_executor(executor, _dailymotion_api, url)
    if result:
        return result
    raise ValueError("Impossible d'extraire cette vidéo Dailymotion.")


# ─── Reddit : JSON API sans authentification ──────────────────────────────────

def _reddit_json(url: str) -> Optional[VideoInfo]:
    """Extrait une vidéo Reddit via leur API JSON publique."""
    clean = re.sub(r'\?.*$', '', url.rstrip('/'))
    if not clean.endswith('.json'):
        clean += '.json'
    api_url = clean + '?raw_json=1&limit=1'

    _hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.7",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    try:
        with httpx.Client(follow_redirects=True, timeout=15, headers=_hdrs) as c:
            resp = c.get(api_url)
            if resp.status_code != 200:
                logger.debug(f"Reddit JSON {resp.status_code} for {api_url[:80]}")
                return None
            data = resp.json()
    except Exception as e:
        logger.debug(f"Reddit JSON parse error: {e}")
        return None

    try:
        post = data[0]["data"]["children"][0]["data"]
    except (KeyError, IndexError, TypeError):
        return None

    # Vidéo Reddit native (v.redd.it)
    media = post.get("media") or post.get("secure_media") or {}
    reddit_video = media.get("reddit_video") or {}
    video_url = reddit_video.get("fallback_url") or reddit_video.get("hls_url")

    if not video_url:
        # Crossposts
        cp = post.get("crosspost_parent_list") or []
        for cp_post in cp:
            cp_media = cp_post.get("media") or {}
            cp_video = cp_media.get("reddit_video") or {}
            video_url = cp_video.get("fallback_url")
            if video_url:
                break

    if not video_url:
        return None

    # Nettoyer les params de tracking
    video_url = re.sub(r'\?.*$', '', video_url)

    title     = post.get("title") or "Vidéo Reddit"
    thumbnail = post.get("thumbnail")
    if thumbnail in ("self", "default", "nsfw", "spoiler", ""):
        thumbnail = None
    duration  = reddit_video.get("duration")
    author    = post.get("author")

    fmt = FormatInfo(format_id="0", ext="mp4", quality="best", url=video_url)
    return VideoInfo(
        original_url=url, title=title[:200], author=author,
        thumbnail=thumbnail, duration=duration,
        platform="reddit",
        formats=[fmt], best_url=video_url, no_watermark_url=video_url,
        required_headers={
            "User-Agent": UA_DESKTOP,
            "Referer": "https://www.reddit.com/",
        },
    )


async def _extract_reddit(url: str) -> VideoInfo:
    loop = asyncio.get_event_loop()

    # ── Cas 1 : URL CDN directe (packaged-media.redd.it / v.redd.it/*.mp4) ──
    if re.search(r'(packaged-media\.redd\.it|v\.redd\.it/[^/]+\.mp4)', url):
        clean = re.sub(r'\?.*$', '', url)
        fmt = FormatInfo(format_id="0", ext="mp4", quality="best", url=clean)
        return VideoInfo(
            original_url=url, title="Vidéo Reddit",
            platform="reddit", formats=[fmt],
            best_url=clean, no_watermark_url=clean,
            required_headers={"User-Agent": UA_DESKTOP, "Referer": "https://www.reddit.com/"},
        )

    # ── Cas 2 : URL courte /s/ → extraire l'URL réelle ───────────────────────
    if re.search(r'reddit\.com/r/[^/]+/s/', url):
        def _resolve_reddit_share(share_url: str) -> str:
            _hdrs = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.7",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Upgrade-Insecure-Requests": "1",
            }
            # Étape 1 : capturer le Location sans suivre la redirection
            try:
                with httpx.Client(follow_redirects=False, timeout=10, headers=_hdrs) as c:
                    r = c.get(share_url)
                    loc = r.headers.get("location", "")
                    if loc and "/comments/" in loc:
                        return loc if loc.startswith("http") else "https://www.reddit.com" + loc
                    # Chercher dans le HTML (page de login / error)
                    m = re.search(
                        r'https?://(?:www\.)?reddit\.com/r/[^/]+/comments/[^"\'>\s]+', r.text
                    )
                    if m:
                        return m.group(0)
            except Exception as e:
                logger.debug(f"Reddit /s/ no-redirect failed: {e}")
            # Étape 2 : suivre la redirection complète
            try:
                with httpx.Client(follow_redirects=True, timeout=12, headers=_hdrs) as c:
                    r = c.get(share_url)
                    final = str(r.url)
                    if "reddit.com" in final and "/comments/" in final:
                        return final
            except Exception as e:
                logger.debug(f"Reddit /s/ follow-redirect failed: {e}")
            return share_url
        resolved = await loop.run_in_executor(executor, _resolve_reddit_share, url)
        if resolved and resolved != url:
            logger.info(f"Reddit /s/ resolved: {url} → {resolved[:80]}")
            url = resolved

        # Si l'URL est toujours une URL /s/ (redirection bloquée), on tente
        # le JSON sur www + old.reddit.com avant d'appeler yt-dlp
        if re.search(r'reddit\.com/r/[^/]+/s/', url):
            def _try_share_json(base: str) -> Optional[VideoInfo]:
                # Essaie POST-like : /s/ID.json → Reddit redirige vers le post
                share_json = re.sub(r'https?://(?:www\.|old\.)?reddit\.com',
                                    base, url.rstrip('/'))
                return _reddit_json(share_json)

            for _base in ("https://old.reddit.com", "https://www.reddit.com"):
                r = await loop.run_in_executor(executor, _try_share_json, _base)
                if r:
                    return r

            raise ValueError(
                "Ce lien de partage Reddit (/s/) ne peut pas être résolu depuis ce serveur. "
                "Copiez l'URL complète du post (reddit.com/r/.../comments/...) et réessayez."
            )

    # ── Cas 3 : yt-dlp ────────────────────────────────────────────────────────
    # Guard : les URLs /s/ non résolues ne doivent jamais arriver ici
    if re.search(r'reddit\.com/r/[^/]+/s/', url):
        raise ValueError(
            "Ce lien de partage Reddit (/s/) ne peut pas être résolu depuis ce serveur. "
            "Copiez l'URL complète du post (reddit.com/r/.../comments/...) et réessayez."
        )
    opts = get_ydl_opts("reddit")
    def _try():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    try:
        info = await loop.run_in_executor(executor, _try)
        if info:
            formats, best_url, no_wm_url, audio_url = _parse_formats(info, "reddit")
            if best_url:
                return VideoInfo(
                    original_url=url, title=info.get("title") or "Vidéo Reddit",
                    author=info.get("uploader"), thumbnail=info.get("thumbnail"),
                    duration=info.get("duration"), view_count=info.get("view_count"),
                    platform="reddit", formats=formats,
                    best_url=best_url, no_watermark_url=no_wm_url or best_url,
                    audio_only_url=audio_url,
                    required_headers=DOWNLOAD_HEADERS.get("reddit", {}),
                )
    except Exception as e:
        logger.debug(f"Reddit yt-dlp failed: {e}")

    logger.info("Reddit: yt-dlp failed, fallback JSON API...")
    result = await loop.run_in_executor(executor, _reddit_json, url)
    if result:
        return result
    raise ValueError(
        "Impossible d'extraire cette vidéo Reddit. "
        "Vérifiez que le post est public et contient une vidéo native."
    )


# ─── Extraction principale ────────────────────────────────────────────────────

async def extract_video_info(url: str, quality: str = "best") -> VideoInfo:
    url      = url.strip()
    platform = detect_platform(url)

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

    if platform == "reddit":
        return await _extract_reddit(url)

    ydl_opts = get_ydl_opts(platform, quality)
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
            raise ValueError("Cette vidéo n'est pas disponible dans votre région.")
        if "Sign in" in msg or "login" in msg.lower() or "authentication" in msg.lower() or "Account authentication" in msg:
            if platform == "instagram":
                raise ValueError("Instagram requiert une connexion — seuls les profils publics sans restriction sont supportés.")
            if platform in ("twitter", "x"):
                raise ValueError("Twitter/X requiert une authentification API. Essayez avec une URL de tweet public avec vidéo.")
            raise ValueError("Cette vidéo nécessite une connexion.")
        if "removed" in msg.lower() or "deleted" in msg.lower():
            raise ValueError("Cette vidéo a été supprimée.")
        if "members only" in msg.lower():
            raise ValueError("Contenu réservé aux membres.")
        raise ValueError(f"Impossible d'extraire : {msg}")
    except Exception as e:
        raise ValueError(f"Erreur inattendue : {str(e)}")

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
    loop     = asyncio.get_event_loop()

    flat_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "socket_timeout": 30,
        "playlistend": limit,
    }

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

    async def _extract_entry(i: int, entry: dict) -> PlaylistItem:
        entry_url = entry.get("url") or entry.get("webpage_url") or ""
        if not entry_url.startswith("http"):
            entry_url = f"https://www.youtube.com/watch?v={entry.get('id', '')}"
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
            {"id": "reddit",      "name": "Reddit",        "no_watermark": False, "notes": "Vidéos v.redd.it"},
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
        raise HTTPException(status_code=500, detail=str(e))


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
    if platform not in PLAYLIST_PLATFORMS and platform != "unknown":
        raise HTTPException(
            status_code=422,
            detail=f"Les playlists ne sont pas supportées pour {platform}"
        )

    try:
        return await extract_playlist_info(url, body.limit)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Playlist error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
