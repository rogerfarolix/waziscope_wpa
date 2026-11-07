"""Extraction Facebook."""
from wz.core import *  # noqa: F401,F403

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
    loop = asyncio.get_running_loop()

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



# Ré-export de tous les noms (y compris _privés) vers les autres modules
__all__ = [n for n in dir() if not n.startswith("__")]
