#!/usr/bin/env python3
"""
WaziScope — Smoke test : une vraie extraction par plateforme.
Remplace le simple contrôle des cookies : on teste ce que voit l'utilisateur.

Usage : venv/bin/python smoke_test.py [--mail] [--base http://127.0.0.1:8032]
Cron  : 0 * * * *  cd .../extractor && venv/bin/python smoke_test.py --mail
Code retour : 0 si tout passe, 1 sinon.
Envoie un mail uniquement quand l'état change (évite le spam horaire).
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

# Vidéos publiques stables (référence yt-dlp ou très anciennes)
SAMPLES = {
    "youtube":     "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "tiktok":      "https://www.tiktok.com/@scout2015/video/6718335390845095173",
    "instagram":   "https://www.instagram.com/reel/Chunk8-jurw/",
    "facebook":    "https://www.facebook.com/radiokicksfm/videos/3676516585958356/",
    "pinterest":   "https://www.pinterest.com/pin/664281013778109217/",
    "dailymotion": "http://www.dailymotion.com/video/x5kesuj_office-christmas-party-review",
    "linkedin":    "https://www.linkedin.com/posts/the-mathworks_2_what-is-mathworks-cloud-center-activity-7151241570371948544-4Gu7",
    "twitch":      "https://clips.twitch.tv/FaintLightGullWholeWheat",
    "rumble":      "https://rumble.com/vdmum1-moose-the-dog-helps-girls-dig-a-snow-fort.html",
    "odysee":      "https://lbry.tv/@Mantega:1/First-day-LBRY:1",
    "bilibili":    "https://www.bilibili.com/video/BV13x41117TL",
    "weibo":       "https://weibo.com/7827771738/N4xlMvjhI",
}

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".smoke_state.json")


def check(base: str, platform: str, url: str) -> tuple[bool, str, float]:
    start = time.time()
    try:
        q = urllib.parse.quote(url, safe="")
        with urllib.request.urlopen(f"{base}/extract?url={q}", timeout=120) as r:
            d = json.load(r)
        ok = bool(d.get("success")) and bool((d.get("data") or {}).get("best_url") or (d.get("data") or {}).get("formats"))
        info = (d.get("data") or {}).get("title") if ok else d.get("error")
    except Exception as e:  # réseau, timeout, JSON invalide
        ok, info = False, str(e)
    return ok, str(info)[:120], time.time() - start


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8032")
    ap.add_argument("--mail", action="store_true", help="mail si l'état change")
    ap.add_argument("--only", help="liste de plateformes séparées par des virgules")
    args = ap.parse_args()

    targets = SAMPLES
    if args.only:
        keep = {p.strip() for p in args.only.split(",")}
        targets = {k: v for k, v in SAMPLES.items() if k in keep}

    results = {}
    for platform, url in targets.items():
        ok, info, secs = check(args.base, platform, url)
        results[platform] = ok
        print(f"{'OK  ' if ok else 'FAIL'} {platform:12} {secs:5.1f}s  {info}", flush=True)

    failed = sorted(p for p, ok in results.items() if not ok)
    print(f"\n{len(results) - len(failed)}/{len(results)} plateformes OK")

    try:
        with open(STATE_FILE) as f:
            previous = json.load(f)
    except Exception:
        previous = {}

    # Un test partiel (--only) complète l'état existant sans l'écraser
    merged = {**previous, **results}

    if args.mail:
        if previous != merged:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from check_cookies import send_email  # réutilise la config SMTP existante
            rows = "".join(
                f"<tr><td>{p}</td><td>{'✅' if ok else '❌'}</td></tr>" for p, ok in results.items()
            )
            subject = f"[WaziScope] {len(failed)} plateforme(s) en échec" if failed else "[WaziScope] Toutes les plateformes OK"
            send_email(subject, f"<h3>{subject}</h3><table border=1 cellpadding=4>{rows}</table>")

    # Toujours enregistrer : lu par GET /status → affiché dans l'interface
    with open(STATE_FILE, "w") as f:
        json.dump(merged, f)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
