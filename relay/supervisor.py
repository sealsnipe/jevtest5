"""Supervisor: keeps relay (uvicorn) and the Cloudflare quick tunnel alive.

- Starts both, restarts whichever exits (backoff 5 s .. 60 s).
- Reads the tunnel URL from cloudflared's output, writes it to log/relay_url.txt,
  sets the Telegram webhook to <url>/telegram (secret from .env) and tells the boss
  via Telegram that the relay (re)started, with the URL.
- Logs to log/supervisor.log.

    python -m relay.supervisor            # foreground (Task Scheduler runs it at logon)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "log"
URL_FILE = LOG_DIR / "relay_url.txt"
LOG_FILE = LOG_DIR / "supervisor.log"
PORT = int(os.environ.get("RELAY_PORT", "8080"))
TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

load_dotenv(ROOT / ".env")


def log(msg: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def cloudflared_bin() -> str:
    for c in (shutil.which("cloudflared"),
              r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
              r"C:\Program Files\cloudflared\cloudflared.exe"):
        if c and Path(c).exists():
            return c
    raise RuntimeError("cloudflared nicht gefunden")


def tg(method: str, **data) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN fehlt"}
    try:
        return requests.post(f"https://api.telegram.org/bot{token}/{method}", data=data, timeout=15).json()
    except requests.RequestException as e:
        return {"ok": False, "description": str(e)}


def notify_chef(text: str) -> None:
    chef = os.environ.get("CHEF_CHAT_ID")
    if chef:
        tg("sendMessage", chat_id=chef, text=text)


def on_new_url(url: str, first: bool) -> None:
    URL_FILE.write_text(url, encoding="utf-8")
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    res = tg("setWebhook", url=f"{url}/telegram", secret_token=secret, allowed_updates='["message"]')
    log(f"tunnel url {url} · setWebhook ok={res.get('ok')} {res.get('description', '')}")
    what = "gestartet" if first else "neu gestartet"
    notify_chef(f"Relay {what}.\nURL: {url}\nWebhook: {'ok' if res.get('ok') else 'FEHLER ' + str(res.get('description'))}")


class Proc:
    def __init__(self, name: str, cmd: list[str], on_line=None):
        self.name, self.cmd, self.on_line = name, cmd, on_line
        self.p: subprocess.Popen | None = None
        self.restarts = 0

    def start(self) -> None:
        self.p = subprocess.Popen(self.cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._pump, daemon=True).start()
        log(f"{self.name} gestartet (pid {self.p.pid})")

    def _pump(self) -> None:
        assert self.p and self.p.stdout
        for line in self.p.stdout:
            if self.on_line:
                self.on_line(line)

    def alive(self) -> bool:
        return self.p is not None and self.p.poll() is None

    def stop(self) -> None:
        if self.alive():
            self.p.terminate()  # type: ignore[union-attr]


def main() -> int:
    py = sys.executable
    relay = Proc("relay", [py, "-m", "uvicorn", "relay.app:app", "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"])
    state = {"url": None, "first": True}

    def tunnel_line(line: str) -> None:
        m = TUNNEL_RE.search(line)
        if m and m.group(0) != state["url"]:
            state["url"] = m.group(0)
            on_new_url(state["url"], state["first"])
            state["first"] = False

    tunnel = Proc("tunnel", [cloudflared_bin(), "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"], on_line=tunnel_line)

    relay.start()
    tunnel.start()
    backoff = {"relay": 5, "tunnel": 5}
    try:
        while True:
            time.sleep(5)
            for proc in (relay, tunnel):
                if not proc.alive():
                    code = proc.p.returncode if proc.p else None
                    proc.restarts += 1
                    log(f"{proc.name} beendet (code {code}), Neustart #{proc.restarts} in {backoff[proc.name]} s")
                    time.sleep(backoff[proc.name])
                    backoff[proc.name] = min(backoff[proc.name] * 2, 60)
                    if proc.name == "tunnel":
                        state["url"] = None  # new URL will be announced + webhook re-set
                    proc.start()
                else:
                    backoff[proc.name] = 5
    except KeyboardInterrupt:
        pass
    finally:
        relay.stop()
        tunnel.stop()
        log("supervisor beendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
