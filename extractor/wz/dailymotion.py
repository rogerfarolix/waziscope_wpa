"""Extraction Dailymotion."""
from wz.core import *  # noqa: F401,F403

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
    loop = asyncio.get_running_loop()
    # Essai yt-dlp sans impersonation
    opts = {**get_ydl_opts("dailymotion"), "impersonate": None}
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



# Ré-export de tous les noms (y compris _privés) vers les autres modules
__all__ = [n for n in dir() if not n.startswith("__")]
