"""Extraction Tiktok."""
from wz.core import *  # noqa: F401,F403

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
        "nocheckcertificate": False,
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
    loop = asyncio.get_running_loop()
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



# Ré-export de tous les noms (y compris _privés) vers les autres modules
__all__ = [n for n in dir() if not n.startswith("__")]
