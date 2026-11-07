"""Extraction Youtube."""
from wz.core import *  # noqa: F401,F403

# ─── Extraction principale ────────────────────────────────────────────────────

def _strip_youtube_list(url: str) -> str:
    """Remove ?list= from YouTube URLs that aren't real playlists (WL, RD mixes, etc.)."""
    import urllib.parse as _up
    try:
        parsed = _up.urlparse(url)
        qs = _up.parse_qs(parsed.query, keep_blank_values=True)
        list_id = (qs.get("list") or [""])[0]
        # Keep real playlists (PL*, UU*, FL*); strip WL and auto-mixes (RD*)
        if list_id and (list_id == "WL" or list_id.startswith("RD")):
            qs.pop("list", None)
            qs.pop("index", None)
            qs.pop("start_radio", None)
            new_query = _up.urlencode({k: v[0] for k, v in qs.items()})
            return _up.urlunparse(parsed._replace(query=new_query))
    except Exception:
        pass
    return url


# ─── Invidious fallback ───────────────────────────────────────────────────────
# Utilisé quand YouTube bloque l'IP datacenter. Invidious fait la requête depuis
# ses propres serveurs (IPs résidentielles / non-datacenter).

_INVIDIOUS_INSTANCES = [
    "https://invidious.io",
    "https://yewtu.be",
    "https://inv.tux.pizza",
    "https://invidious.nerdvpn.de",
    "https://yt.artemislena.eu",
]

def _extract_yt_video_id(url: str) -> str | None:
    """Extrait l'ID vidéo depuis une URL YouTube."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

async def _youtube_via_invidious(url: str, quality: str = "best") -> VideoInfo:
    """
    Fallback YouTube via API Invidious.
    Contourne le blocage IP datacenter en passant par les serveurs Invidious.
    Retourne jusqu'à 720p (formatStreams progressifs, vidéo+audio combinés).
    """
    video_id = _extract_yt_video_id(url)
    if not video_id:
        raise ValueError("ID vidéo YouTube introuvable dans l'URL.")

    last_err: Exception = ValueError("Toutes les instances Invidious ont échoué.")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for instance in _INVIDIOUS_INSTANCES:
            api_url = f"{instance}/api/v1/videos/{video_id}?fields=title,author,lengthSeconds,viewCount,description,videoThumbnails,formatStreams,adaptiveFormats"
            try:
                r = await client.get(api_url)
                if r.status_code != 200:
                    continue
                data = r.json()
            except Exception as e:
                last_err = e
                continue

            if data.get("error"):
                last_err = ValueError(data["error"])
                continue

            # Thumbnails
            thumbnails = data.get("videoThumbnails") or []
            thumbnail  = next(
                (t["url"] for t in thumbnails if t.get("quality") in ("maxres", "high", "medium")),
                thumbnails[0]["url"] if thumbnails else None,
            )
            if thumbnail and thumbnail.startswith("/"):
                thumbnail = f"{instance}{thumbnail}"

            # formatStreams = progressive (vidéo+audio, max 720p)
            fmt_streams = data.get("formatStreams") or []
            formats: list[FormatInfo] = []
            best_url: str | None = None
            audio_url: str | None = None

            # Résolution souhaitée
            _quality_map = {"4k": 2160, "1080": 1080, "720": 720, "480": 480, "360": 360}
            want_h = _quality_map.get(quality, 0)

            for s in fmt_streams:
                stream_url = s.get("url")
                if not stream_url:
                    continue
                label   = s.get("qualityLabel", s.get("quality", ""))
                itag    = str(s.get("itag", ""))
                height  = int(label.replace("p", "").split("@")[0]) if label and "p" in label else None
                ext     = s.get("container", "mp4")

                fmt = FormatInfo(
                    format_id=itag,
                    ext=ext,
                    quality=label,
                    url=stream_url,
                    width=s.get("size", "x").split("x")[0] if "size" in s else None,
                    height=height,
                    fps=s.get("fps"),
                )
                formats.append(fmt)

                if height:
                    if want_h and height == want_h:
                        best_url = stream_url
                    elif not best_url or height > (int(str(formats[-2].quality).replace("p", "").split("@")[0]) if len(formats) > 1 else 0):
                        best_url = stream_url

            # adaptiveFormats pour l'audio seul
            for s in (data.get("adaptiveFormats") or []):
                mime = s.get("type", "")
                if mime.startswith("audio/") and not audio_url:
                    audio_url = s.get("url")

            if not formats:
                last_err = ValueError("Aucun format disponible via Invidious.")
                continue

            if not best_url and formats:
                best_url = formats[-1].url

            logger.info(f"[invidious] Fallback OK via {instance} pour {video_id}")
            return VideoInfo(
                original_url=url,
                title=data.get("title") or "Vidéo sans titre",
                description=data.get("description"),
                author=data.get("author"),
                thumbnail=thumbnail,
                duration=data.get("lengthSeconds"),
                view_count=data.get("viewCount"),
                platform="youtube",
                formats=formats,
                best_url=best_url,
                audio_only_url=audio_url,
                required_headers={},
            )

    raise last_err



# Ré-export de tous les noms (y compris _privés) vers les autres modules
__all__ = [n for n in dir() if not n.startswith("__")]
