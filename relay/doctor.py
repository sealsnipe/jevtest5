"""Doctor: independent health check for the relay, alerts the boss via Telegram.

Runs from Task Scheduler every 10 minutes, separate from the relay process, so it
still works when the relay is dead. Checks:

  1. relay answers on 127.0.0.1:<port>/health
  2. relay answers through the tunnel (URL from log/relay_url.txt)
  3. Telegram getWebhookInfo: url matches the tunnel, no last_error, no backlog

Alerts go to CHEF_CHAT_ID with a cooldown (log/doctor_state.json) so a dead relay
produces one message per hour, not one every 10 minutes. Recovery is reported once.

    python -m relay.doctor            # exit 0 = healthy, 1 = problems
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "log"
URL_FILE = LOG_DIR / "relay_url.txt"
STATE_FILE = LOG_DIR / "doctor_state.json"
PORT = int(os.environ.get("RELAY_PORT", "8080"))
ALERT_COOLDOWN_S = 3600
BACKLOG_WARN = 5

load_dotenv(ROOT / ".env")


def check() -> list[str]:
    problems: list[str] = []
    try:
        r = requests.get(f"http://127.0.0.1:{PORT}/health", timeout=5)
        if r.status_code != 200:
            problems.append(f"lokal: HTTP {r.status_code}")
    except requests.RequestException as e:
        problems.append(f"lokal: nicht erreichbar ({type(e).__name__})")

    url = URL_FILE.read_text(encoding="utf-8").strip() if URL_FILE.exists() else ""
    if not url:
        problems.append("tunnel: keine URL bekannt (Supervisor nie gelaufen?)")
    else:
        try:
            r = requests.get(f"{url}/health", timeout=10)
            if r.status_code != 200:
                problems.append(f"tunnel: HTTP {r.status_code}")
        except requests.RequestException as e:
            problems.append(f"tunnel: nicht erreichbar ({type(e).__name__})")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        try:
            info = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10).json().get("result", {})
            if url and info.get("url") != f"{url}/telegram":
                problems.append(f"webhook: zeigt auf {info.get('url') or 'nichts'}, erwartet {url}/telegram")
            if info.get("last_error_message"):
                age = int(time.time()) - int(info.get("last_error_date", 0))
                if age < 1800:
                    problems.append(f"webhook: Telegram meldet '{info['last_error_message']}' (vor {age // 60} min)")
            if int(info.get("pending_update_count", 0)) >= BACKLOG_WARN:
                problems.append(f"webhook: {info['pending_update_count']} Updates stauen sich")
        except requests.RequestException as e:
            problems.append(f"telegram: API nicht erreichbar ({type(e).__name__})")
    else:
        problems.append("TELEGRAM_BOT_TOKEN fehlt in .env")
    return problems


def notify(text: str) -> None:
    token, chef = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("CHEF_CHAT_ID")
    if token and chef:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chef, "text": text}, timeout=15)
        except requests.RequestException:
            pass


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    problems = check()
    now = time.time()
    line = f"{datetime.now().isoformat(timespec='seconds')} {'OK' if not problems else 'PROBLEME: ' + ' | '.join(problems)}"
    with (LOG_DIR / "doctor.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)

    if problems:
        if now - state.get("last_alert", 0) > ALERT_COOLDOWN_S:
            notify("⚠️ Relay-Check:\n- " + "\n- ".join(problems))
            state["last_alert"] = now
        state["unhealthy"] = True
    elif state.get("unhealthy"):
        notify("✅ Relay wieder gesund.")
        state["unhealthy"] = False
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
