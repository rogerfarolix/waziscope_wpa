"""Extraction Pinterest."""
from wz.core import *  # noqa: F401,F403

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
    loop = asyncio.get_running_loop()

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



# Ré-export de tous les noms (y compris _privés) vers les autres modules
__all__ = [n for n in dir() if not n.startswith("__")]
