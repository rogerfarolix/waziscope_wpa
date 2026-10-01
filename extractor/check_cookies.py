#!/usr/bin/env python3
"""
WaziScope — Vérification des cookies YouTube + alerte email.
Usage : python3 check_cookies.py
Cron  : 0 9 * * 1  /path/to/venv/bin/python3 /path/to/check_cookies.py
"""

import os
import sys
import time
import smtplib
import http.cookiejar
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

# ─── Config ───────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(SCRIPT_DIR, "youtube_cookies.txt")

MAIL_HOST     = os.getenv("MAIL_HOST",     "mail30.lwspanel.com")
MAIL_PORT     = int(os.getenv("MAIL_PORT", "587"))
MAIL_USER     = os.getenv("MAIL_USERNAME", "contact@nealix.org")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM     = os.getenv("MAIL_FROM_ADDRESS", "contact@nealix.org")
MAIL_TO       = os.getenv("COOKIE_ALERT_EMAIL", "rogergnanih66@gmail.com")

# Jours avant expiration pour déclencher l'alerte
WARN_DAYS = 30

# ─── Helpers ──────────────────────────────────────────────────────────────────

def send_email(subject: str, body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Waziscope <{MAIL_FROM}>"
        msg["To"]      = MAIL_TO
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(MAIL_USER, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, [MAIL_TO], msg.as_string())
        print(f"[OK] Email envoyé à {MAIL_TO}")
        return True
    except Exception as e:
        print(f"[ERR] Email échoué : {e}", file=sys.stderr)
        return False


def check_cookies() -> dict:
    """
    Lit le fichier Netscape cookies.txt et retourne un résumé
    de l'état des cookies YouTube critiques.
    """
    if not os.path.isfile(COOKIES_FILE):
        return {"status": "missing", "message": "Fichier cookies introuvable"}

    now        = time.time()
    critical   = {"SAPISID", "SID", "HSID", "__Secure-1PSID", "__Secure-3PSID"}
    found      = {}
    soonest_expiry = None

    try:
        with open(COOKIES_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                domain, _, path, secure, expiry_str, name, value = parts[:7]
                if "youtube.com" not in domain and "google.com" not in domain:
                    continue
                if name not in critical:
                    continue
                try:
                    expiry = int(expiry_str)
                except ValueError:
                    continue

                found[name] = expiry
                if soonest_expiry is None or expiry < soonest_expiry:
                    soonest_expiry = expiry

    except Exception as e:
        return {"status": "error", "message": str(e)}

    if not found:
        return {"status": "empty", "message": "Aucun cookie YouTube critique trouvé"}

    missing = critical - set(found.keys())

    if soonest_expiry == 0:
        # Session cookie (pas d'expiration fixe) — considéré valide
        return {"status": "ok", "found": list(found.keys()), "missing": list(missing)}

    days_left = (soonest_expiry - now) / 86400

    if days_left < 0:
        return {
            "status":    "expired",
            "days_left": int(days_left),
            "message":   f"Cookies expirés depuis {int(-days_left)} jour(s)",
        }

    if days_left < WARN_DAYS:
        return {
            "status":    "expiring_soon",
            "days_left": int(days_left),
            "expiry_date": datetime.fromtimestamp(soonest_expiry, tz=timezone.utc).strftime("%d/%m/%Y"),
            "message":   f"Cookies expirent dans {int(days_left)} jour(s)",
        }

    return {
        "status":    "ok",
        "days_left": int(days_left),
        "expiry_date": datetime.fromtimestamp(soonest_expiry, tz=timezone.utc).strftime("%d/%m/%Y"),
        "found":     list(found.keys()),
        "missing":   list(missing),
    }


def build_email_body(result: dict) -> tuple[str, str]:
    status = result.get("status")

    if status == "missing":
        subject = "⚠️ WaziScope — Cookies YouTube manquants"
        body = """
        <p>Le fichier <code>youtube_cookies.txt</code> est introuvable sur le serveur.</p>
        <p>Les vidéos YouTube restreintes vont échouer.</p>
        """
    elif status == "expired":
        subject = "🔴 WaziScope — Cookies YouTube expirés"
        body = f"""
        <p>Les cookies YouTube sont <strong>expirés depuis {abs(result.get('days_left',0))} jour(s)</strong>.</p>
        <p>Les vidéos YouTube restreintes échouent déjà.</p>
        """
    elif status == "expiring_soon":
        subject = f"🟡 WaziScope — Cookies YouTube expirent dans {result.get('days_left')} jours"
        body = f"""
        <p>Les cookies YouTube expirent le <strong>{result.get('expiry_date')}</strong>
        (dans <strong>{result.get('days_left')} jours</strong>).</p>
        """
    elif status == "empty":
        subject = "⚠️ WaziScope — Cookies YouTube incomplets"
        body = "<p>Aucun cookie critique YouTube (SID, SAPISID…) trouvé dans le fichier.</p>"
    else:
        return "", ""  # status == "ok" → pas d'email

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;color:#1a1a1a;max-width:560px;margin:32px auto">
  <div style="background:#080b0f;padding:20px 24px;border-radius:12px 12px 0 0">
    <span style="color:#1bffa4;font-weight:700;font-size:18px">Wazi<em style="font-style:normal">Scope</em></span>
  </div>
  <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 12px 12px">
    {body}
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
    <p style="font-size:13px;color:#6b7280">
      Pour renouveler les cookies :<br>
      1. Installe <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc">Get cookies.txt LOCALLY</a> sur Chrome<br>
      2. Connecte-toi à YouTube et exporte <code>youtube.com_cookies.txt</code><br>
      3. <code>scp cookies.txt nealix:/var/www/Projets/nealix/waziscope_wpa/extractor/youtube_cookies.txt</code><br>
      4. <code>ssh nealix "sudo supervisorctl restart waziscope-extractor"</code>
    </p>
  </div>
</body></html>"""

    return subject, html


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = check_cookies()
    print(f"[cookies] status={result['status']}  {result.get('message','')}")

    subject, body = build_email_body(result)
    if subject:
        send_email(subject, body)
    else:
        print("[cookies] Cookies OK — aucun email envoyé.")
