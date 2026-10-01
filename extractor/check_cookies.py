#!/usr/bin/env python3
"""
WaziScope — Vérification cookies YouTube + santé yt-dlp + alerte email.
Usage : python3 check_cookies.py
Cron  : 0 9 * * 1  /var/www/Projets/nealix/waziscope_wpa/extractor/run_cookie_check.sh
"""

import os
import sys
import time
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

# ─── Config ───────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(SCRIPT_DIR, "youtube_cookies.txt")
VENV_YTDLP   = os.path.join(SCRIPT_DIR, "venv", "bin", "yt-dlp")

MAIL_HOST     = os.getenv("MAIL_HOST",         "mail30.lwspanel.com")
MAIL_PORT     = int(os.getenv("MAIL_PORT",     "587"))
MAIL_USER     = os.getenv("MAIL_USERNAME",     "contact@nealix.org")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD",     "")
MAIL_FROM     = os.getenv("MAIL_FROM_ADDRESS", "contact@nealix.org")
MAIL_TO       = os.getenv("COOKIE_ALERT_EMAIL","rogergnanih66@gmail.com")

WARN_DAYS     = 30   # alerter X jours avant expiration
# Vidéo de test YouTube publique (toujours disponible)
TEST_VIDEO    = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
# Vidéo qui nécessite les cookies (restreinte)
TEST_RESTRICTED = "https://www.youtube.com/watch?v=2HaUgNmpV8Q"

# ─── Email ────────────────────────────────────────────────────────────────────

def send_email(subject: str, html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Waziscope <{MAIL_FROM}>"
        msg["To"]      = MAIL_TO
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=15) as srv:
            srv.ehlo(); srv.starttls(); srv.login(MAIL_USER, MAIL_PASSWORD)
            srv.sendmail(MAIL_FROM, [MAIL_TO], msg.as_string())
        print(f"[mail] Envoyé à {MAIL_TO}")
        return True
    except Exception as e:
        print(f"[mail] ERREUR : {e}", file=sys.stderr)
        return False

# ─── Check cookies ────────────────────────────────────────────────────────────

def check_cookies() -> dict:
    if not os.path.isfile(COOKIES_FILE):
        return {"status": "missing", "message": "Fichier youtube_cookies.txt introuvable"}

    now      = time.time()
    critical = {"SAPISID", "SID", "HSID", "__Secure-1PSID", "__Secure-3PSID"}
    found    = {}
    soonest  = None

    with open(COOKIES_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _, _, _, expiry_str, name, _ = parts[:7]
            if "youtube.com" not in domain and "google.com" not in domain:
                continue
            if name not in critical:
                continue
            try:
                expiry = int(expiry_str)
            except ValueError:
                continue
            found[name] = expiry
            if expiry > 0 and (soonest is None or expiry < soonest):
                soonest = expiry

    if not found:
        return {"status": "empty", "message": "Aucun cookie critique YouTube trouvé"}

    if soonest is None:
        return {"status": "ok", "found": list(found.keys()), "days_left": None}

    days_left = (soonest - now) / 86400
    expiry_date = datetime.fromtimestamp(soonest, tz=timezone.utc).strftime("%d/%m/%Y")

    if days_left < 0:
        return {"status": "expired",  "days_left": int(days_left), "expiry_date": expiry_date}
    if days_left < WARN_DAYS:
        return {"status": "expiring_soon", "days_left": int(days_left), "expiry_date": expiry_date}
    return {"status": "ok", "days_left": int(days_left), "expiry_date": expiry_date}

# ─── Check yt-dlp ─────────────────────────────────────────────────────────────

def check_ytdlp() -> dict:
    """Vérifie la version yt-dlp et teste une extraction YouTube réelle."""
    ytdlp = VENV_YTDLP if os.path.isfile(VENV_YTDLP) else "yt-dlp"

    # Version
    try:
        version = subprocess.check_output([ytdlp, "--version"], timeout=10, text=True).strip()
    except Exception as e:
        return {"status": "missing", "message": f"yt-dlp introuvable : {e}"}

    # Test extraction vidéo publique
    try:
        result = subprocess.run(
            [ytdlp,
             "--cookies", COOKIES_FILE,
             "--js-runtimes", "node:/usr/bin/node",
             "--remote-components", "ejs:github",
             "--extractor-args", "youtube:player_client=ios,android_vr,web",
             "--no-playlist", "--get-title",
             TEST_VIDEO],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {
                "status": "broken",
                "version": version,
                "message": result.stderr.strip().splitlines()[-1] if result.stderr else "Extraction échouée",
            }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "version": version, "message": "Timeout lors de l'extraction test"}
    except Exception as e:
        return {"status": "error", "version": version, "message": str(e)}

    # Test vidéo restreinte (nécessite cookies)
    restricted_ok = False
    try:
        r2 = subprocess.run(
            [ytdlp,
             "--cookies", COOKIES_FILE,
             "--js-runtimes", "node:/usr/bin/node",
             "--remote-components", "ejs:github",
             "--extractor-args", "youtube:player_client=ios,android_vr,web",
             "--no-playlist", "--get-title",
             TEST_RESTRICTED],
            capture_output=True, text=True, timeout=60
        )
        restricted_ok = r2.returncode == 0 and bool(r2.stdout.strip())
    except Exception:
        pass

    return {
        "status":        "ok",
        "version":       version,
        "public_ok":     True,
        "restricted_ok": restricted_ok,
    }

# ─── Email builder ────────────────────────────────────────────────────────────

RENEW_STEPS = """
<ol style="line-height:2">
  <li>Installe <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc">Get cookies.txt LOCALLY</a> sur Chrome</li>
  <li>Connecte-toi sur <a href="https://youtube.com">youtube.com</a></li>
  <li>Clique sur l'extension → exporte <code>youtube.com_cookies.txt</code></li>
  <li><code>scp cookies.txt nealix:/var/www/Projets/nealix/waziscope_wpa/extractor/youtube_cookies.txt</code></li>
  <li><code>ssh nealix "sudo supervisorctl restart waziscope-extractor"</code></li>
</ol>
"""

def build_email(cookie_result: dict, ytdlp_result: dict) -> tuple[str, str]:
    problems = []
    warnings = []

    # Cookies
    cs = cookie_result["status"]
    if cs == "missing":
        problems.append("❌ Fichier <code>youtube_cookies.txt</code> <strong>introuvable</strong> sur le serveur")
    elif cs == "expired":
        problems.append(f"❌ Cookies YouTube <strong>expirés</strong> depuis {abs(cookie_result['days_left'])} jour(s)")
    elif cs == "empty":
        problems.append("❌ Cookies YouTube <strong>vides</strong> — aucun cookie critique trouvé")
    elif cs == "expiring_soon":
        warnings.append(f"⚠️ Cookies expirent le <strong>{cookie_result['expiry_date']}</strong> (dans {cookie_result['days_left']} jours)")

    # yt-dlp
    ys = ytdlp_result["status"]
    version = ytdlp_result.get("version", "?")
    if ys == "missing":
        problems.append(f"❌ yt-dlp <strong>introuvable</strong> : {ytdlp_result.get('message')}")
    elif ys in ("broken", "error", "timeout"):
        problems.append(f"❌ yt-dlp <strong>cassé</strong> (v{version}) : {ytdlp_result.get('message')}")
    elif ys == "ok":
        if not ytdlp_result.get("restricted_ok"):
            warnings.append(f"⚠️ yt-dlp v{version} OK mais les vidéos <strong>restreintes échouent</strong> (cookies invalides ?)")

    if not problems and not warnings:
        return "", ""  # tout va bien

    severity = "🔴 Problème" if problems else "🟡 Avertissement"
    subject  = f"{severity} WaziScope — YouTube extraction"

    rows = "".join(f'<li style="margin:6px 0">{p}</li>' for p in problems + warnings)

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;color:#1a1a1a;max-width:560px;margin:32px auto">
  <div style="background:#080b0f;padding:20px 24px;border-radius:12px 12px 0 0">
    <span style="color:#1bffa4;font-weight:700;font-size:18px">Wazi<em style="font-style:normal">Scope</em></span>
    <span style="color:#7a8499;font-size:13px;margin-left:12px">Rapport hebdomadaire</span>
  </div>
  <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 12px 12px">
    <ul style="padding-left:20px">{rows}</ul>

    {"<h3>Renouveler les cookies</h3>" + RENEW_STEPS if problems or not ytdlp_result.get('restricted_ok') else ""}

    <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
    <p style="font-size:12px;color:#9ca3af">
      yt-dlp v{version} · cookies : {cookie_result.get('expiry_date','?')} ·
      {datetime.now(tz=timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC
    </p>
  </div>
</body></html>"""

    return subject, html

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] WaziScope cookie & yt-dlp check")

    cookie_result = check_cookies()
    print(f"[cookies] {cookie_result['status']}  {cookie_result.get('message') or cookie_result.get('expiry_date','')}")

    ytdlp_result = check_ytdlp()
    print(f"[yt-dlp]  {ytdlp_result['status']}  v{ytdlp_result.get('version','?')}  "
          f"public={'✓' if ytdlp_result.get('public_ok') else '✗'}  "
          f"restricted={'✓' if ytdlp_result.get('restricted_ok') else '✗'}")

    subject, html = build_email(cookie_result, ytdlp_result)
    if subject:
        send_email(subject, html)
    else:
        print("[check] Tout OK — aucun email envoyé.")
