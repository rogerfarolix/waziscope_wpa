"""Tests unitaires extracteur — sans réseau. Lancer : venv/bin/python -m pytest tests"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import main  # noqa: E402


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://youtu.be/abc", "youtube"),
    ("https://vm.tiktok.com/ZM123/", "tiktok"),
    ("https://pin.it/abc", "pinterest"),
    ("https://fb.watch/abc", "facebook"),
    ("https://x.com/a/status/1", "twitter"),
    ("https://www.instagram.com/reel/abc/", "instagram"),
    ("https://odysee.com/@a:1/b:2", "odysee"),
    ("https://b23.tv/abc", "bilibili"),
    ("https://example.com/video.mp4", "unknown"),
])
def test_detect_platform(url, expected):
    assert main.detect_platform(url) == expected


def test_friendly_error_hides_raw_ytdlp():
    raw = "ERROR: [Rumble] x: Unable to download webpage: HTTP Error 403: Forbidden"
    msg = main._friendly_error(raw, "rumble")
    assert "ERROR" not in msg and "Rumble" in msg


def test_friendly_error_fallback():
    assert "ERROR" not in main._friendly_error("ERROR: something odd", "vimeo")


def test_youtube_never_impersonated():
    assert "impersonate" not in main.get_ydl_opts("youtube")


def test_proxy_only_on_listed_platforms(monkeypatch):
    monkeypatch.setattr(main, "_PROXY_URL", "http://proxy:1")
    monkeypatch.setattr(main, "_PROXY_PLATFORMS", {"rumble"})
    assert main.get_ydl_opts("rumble")["proxy"] == "http://proxy:1"
    assert "proxy" not in main.get_ydl_opts("tiktok")
