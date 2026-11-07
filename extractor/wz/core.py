"""Socle commun : config, schémas, détection, options yt-dlp, helpers."""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
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

# Cookies YouTube — chemin relatif au répertoire du script.
# Présence optionnelle : si absent, yt-dlp fonctionne sans (vidéos publiques).
import os as _os
import subprocess as _subprocess

_BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_COOKIES_PATH: str | None = None
for _candidate in [
    _os.path.join(_BASE_DIR, "youtube_cookies.txt"),
    _os.path.join(_BASE_DIR, "cookies.txt"),
]:
    if _os.path.isfile(_candidate):
        _COOKIES_PATH = _candidate
        break

if _COOKIES_PATH:
    logger.info(f"Cookies YouTube chargés : {_COOKIES_PATH}")
else:
    logger.warning("Pas de fichier cookies YouTube — les vidéos restreintes échoueront.")

# Démarrer le serveur bgutil (PO token provider) s'il est installé.
# bgutil génère des Proof-of-Origin tokens pour YouTube sans cookies.
_BGUTIL_JS = _os.path.expanduser("~/bgutil-ytdlp-pot-provider/server/build/main.js")
if _os.path.isfile(_BGUTIL_JS):
    try:
        _subprocess.Popen(
            ["/usr/bin/node", _BGUTIL_JS, "--host", "127.0.0.1"],
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("bgutil PO token server démarré sur 127.0.0.1:4416")
    except Exception as _e:
        logger.warning(f"Impossible de démarrer bgutil : {_e}")
else:
    logger.warning(f"bgutil non trouvé ({_BGUTIL_JS}) — PO tokens non disponibles.")

# Impersonation navigateur (nécessite curl_cffi)
try:
    import curl_cffi  # noqa: F401
    from yt_dlp.networking.impersonate import ImpersonateTarget
    _IMPERSONATE_TARGET = ImpersonateTarget("chrome")
except Exception:
    _IMPERSONATE_TARGET = None
    logger.warning("curl_cffi absent — impersonation navigateur désactivée.")

# YouTube : l'impersonation casse le client web + PO tokens bgutil.
_NO_IMPERSONATE = {"youtube"}

# Proxy (ex: http://user:pass@host:port) pour plateformes bannissant les IP datacenter
_PROXY_URL = _os.environ.get("WAZISCOPE_PROXY_URL", "").strip() or None
_PROXY_PLATFORMS = set(
    p.strip() for p in _os.environ.get(
        "WAZISCOPE_PROXY_PLATFORMS", "youtube,rumble,bilibili,vimeo"
    ).split(",") if p.strip()
)
if _PROXY_URL:
    logger.info(f"Proxy actif pour : {sorted(_PROXY_PLATFORMS)}")


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

# Formats vidéo selon la qualité demandée (partagés entre YouTube et Vimeo)
_YT_FORMATS: dict[str, str] = {
    "4k":    "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best",
    "1080":  "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
    "720":   "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
    "480":   "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
    "audio": "bestaudio[ext=m4a]/bestaudio",
    "best":  "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best",
}
_DEFAULT_FORMAT = "best[ext=mp4]/bestvideo+bestaudio/best"

# Surcharges par plateforme : fusionnées sur la config de base.
# Clés spéciales : "__ua" remplace le User-Agent, "__extra_headers" ajoute des headers.
_PLATFORM_OVERRIDES: dict[str, dict] = {
    "tiktok": {
        "format": "bestvideo+bestaudio/best",
        "__ua": UA_ANDROID,
        "__extra_headers": {"Referer": "https://www.tiktok.com/"},
        "extractor_args": {
            "tiktok": {
                "webpage_download": ["0"],
                "api_hostname": ["api16-normal-c-alisg.tiktokv.com"],
                "app_name": ["tiktok"],
                "app_version": ["35.1.2"],
                "manifest_app_version": ["351"],
            }
        },
    },
    "youtube": {
        "__yt_quality": True,          # utilise _YT_FORMATS[quality]
        "merge_output_format": "mp4",
        "__extra_headers": {"Referer": "https://www.youtube.com/"},
        # yt-dlp >= 2026.08 : ios/android_vr retournent LOGIN_REQUIRED depuis IP datacenter.
        # web + bgutil (PO tokens) + Node.js (N-challenge) = meilleur combo serveur.
        # bgutil est démarré automatiquement au startup (voir code startup ci-dessus).
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
            }
        },
        # Python API : dict {runtime: {path?}} — différent de la CLI --js-runtimes
        "js_runtimes": {"node": {"path": "/usr/bin/node"}},
        "__youtube_cookies": True,      # sentinelle : get_ydl_opts injecte cookies si dispo
    },
    "pinterest": {
        "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best",
        "__ua": UA_MOBILE,
        "__extra_headers": {
            "Referer": "https://www.pinterest.com/",
            "X-Pinterest-AppState": "active",
        },
    },
    "facebook": {
        "format": "best[ext=mp4]/bestvideo+bestaudio/best",
        "__ua": UA_ANDROID,
        "__extra_headers": {
            "Referer": "https://www.facebook.com/",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
        },
    },
    "instagram": {
        "format": "best[ext=mp4]/best",
        "__ua": UA_ANDROID,
        "__extra_headers": {
            "Referer": "https://www.instagram.com/",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
        },
    },
    "linkedin": {
        "format": "best[ext=mp4]/best",
        "__extra_headers": {"Referer": "https://www.linkedin.com/"},
    },
    "twitter": {
        "format": _DEFAULT_FORMAT,
        "__extra_headers": {"Referer": "https://twitter.com/"},
    },
    "dailymotion": {
        "format": _DEFAULT_FORMAT,
        "__extra_headers": {"Referer": "https://www.dailymotion.com/"},
    },
    "vimeo": {
        "__yt_quality": True,
        "merge_output_format": "mp4",
        "__extra_headers": {"Referer": "https://vimeo.com/"},
    },
    "twitch": {
        "format": _DEFAULT_FORMAT,
        "__extra_headers": {"Referer": "https://www.twitch.tv/"},
    },
    "rumble": {
        "format": _DEFAULT_FORMAT,
        "__extra_headers": {"Referer": "https://rumble.com/"},
    },
    "odysee": {
        "format": _DEFAULT_FORMAT,
        "__extra_headers": {"Referer": "https://odysee.com/"},
    },
    "snapchat": {
        "format": "best[ext=mp4]/best",
        "__ua": UA_MOBILE,
        "__extra_headers": {"Referer": "https://www.snapchat.com/"},
    },
    "bilibili": {
        "format": "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
        "__extra_headers": {"Referer": "https://www.bilibili.com/"},
    },
}


def get_ydl_opts(platform: str, quality: str = "best") -> dict:
    base: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "nocheckcertificate": False,
        "http_headers": {
            "User-Agent": UA_DESKTOP,
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "format": _DEFAULT_FORMAT,
    }

    overrides = {**_PLATFORM_OVERRIDES.get(platform, {})}  # copie pour ne pas muter le dict global

    # Résoudre le format qualité si la plateforme le demande
    if overrides.pop("__yt_quality", False):
        base["format"] = _YT_FORMATS.get(quality, _YT_FORMATS["best"])

    # Injecter cookies YouTube si disponibles (bgutil gère les PO tokens)
    if overrides.pop("__youtube_cookies", False) and _COOKIES_PATH:
        base["cookiefile"] = _COOKIES_PATH

    # Fusionner User-Agent et headers supplémentaires
    ua = overrides.pop("__ua", None)
    extra_headers = overrides.pop("__extra_headers", {})

    merged_headers = {**base["http_headers"]}
    if ua:
        merged_headers["User-Agent"] = ua
    merged_headers.update(extra_headers)

    base.update(overrides)
    base["http_headers"] = merged_headers

    # Impersonation TLS navigateur (curl_cffi) — contourne une partie des
    # blocages anti-bot (Instagram notamment). Ignoré si curl_cffi absent.
    if _IMPERSONATE_TARGET is not None and platform not in _NO_IMPERSONATE:
        base["impersonate"] = _IMPERSONATE_TARGET

    # Proxy résidentiel optionnel pour les plateformes qui bannissent les IP
    # datacenter (YouTube, Rumble, Bilibili…). Configurer WAZISCOPE_PROXY_URL.
    if _PROXY_URL and platform in _PROXY_PLATFORMS:
        base["proxy"] = _PROXY_URL
    return base


def _friendly_error(msg: str, platform: str) -> str:
    """Traduit une erreur brute yt-dlp en message lisible (sans jargon technique)."""
    low = msg.lower()
    name = platform.capitalize() if platform != "twitter" else "Twitter/X"
    if "403" in low or "412" in low or "blocked" in low or "forbidden" in low:
        return f"{name} bloque temporairement notre serveur. Réessayez plus tard."
    if "404" in low or "does not exist" in low or "not found" in low:
        return "Vidéo introuvable : vérifiez le lien (elle a peut-être été supprimée)."
    if "no video could be found" in low or "no video formats" in low:
        return "Aucune vidéo trouvée à cette adresse."
    if "unsupported url" in low:
        return "Ce type de lien n'est pas pris en charge. Utilisez le lien direct de la vidéo."
    if "logged-in" in low or "login" in low or "cookies" in low:
        return f"{name} exige une connexion pour cette vidéo."
    if "timed out" in low or "timeout" in low:
        return f"{name} met trop de temps à répondre. Réessayez."
    return f"Impossible d'extraire cette vidéo {name}. Le lien est peut-être privé ou non pris en charge."


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



# Ré-export de tous les noms (y compris _privés) vers les autres modules
__all__ = [n for n in dir() if not n.startswith("__")]
