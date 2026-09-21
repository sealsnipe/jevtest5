"""Relay: Telegram Bot-API webhook -> Jev gatekeeper -> Grok Bot webhook.

Telegram can only send its own secret header, Grok Bot's webhook trigger needs
`Authorization: Bearer <key>`. This tiny service sits in between and additionally
runs Layer 1+3 (gatekeeper) so Grok Bot is only woken for real requests.

    uvicorn relay.app:app --host 0.0.0.0 --port 8080

Environment (see .env.example): TELEGRAM_WEBHOOK_SECRET, GROKBOT_WEBHOOK_URL,
GROKBOT_WEBHOOK_KEY, OPENROUTER_API_KEY. Loaded from .env if present.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header, Request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from layers import gatekeeper  # noqa: E402

LOG_DIR = Path(os.environ.get("RELAY_LOG_DIR", Path(__file__).resolve().parent.parent / "log"))
WAKE_ACTIONS = {"queue", "urgent"}
VOICE_PENDING = "voice_pending"

app = FastAPI(title="Projekt Sekretärin – Relay")


def _log(action: str, record: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    with (LOG_DIR / f"{action}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _extract(update: dict[str, Any]) -> dict[str, Any] | None:
    """Pull text / voice info out of a Telegram update. None if nothing usable."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None
    sender = msg.get("from", {})
    base = {
        "chat_id": msg.get("chat", {}).get("id"),
        "message_id": msg.get("message_id"),
        "from": {
            "id": sender.get("id"),
            "username": sender.get("username"),
            "first_name": sender.get("first_name"),
            "last_name": sender.get("last_name"),
        },
    }
    if msg.get("text"):
        return {**base, "text": msg["text"], "voice_file": None}
    if msg.get("voice"):
        return {**base, "text": VOICE_PENDING, "voice_file": msg["voice"].get("file_id")}
    return None


def _wake_grokbot(payload: dict[str, Any]) -> int | None:
    url = os.environ.get("GROKBOT_WEBHOOK_URL")
    key = os.environ.get("GROKBOT_WEBHOOK_KEY")
    if not url or not key:
        _log("error", {"reason": "GROKBOT_WEBHOOK_URL/KEY nicht gesetzt", "payload": payload})
        return None
    try:
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=15)
        return r.status_code
    except requests.RequestException as e:
        _log("error", {"reason": f"grokbot webhook: {e}", "payload": payload})
        return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram")
async def telegram(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    # Always answer 200, otherwise Telegram retries the update forever.
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if not expected or x_telegram_bot_api_secret_token != expected:
        _log("rejected", {"reason": "bad secret header"})
        return {"ok": False, "reason": "unauthorized"}

    update = await request.json()
    item = _extract(update)
    if item is None:
        return {"ok": True, "action": "ignored"}

    # Voice notes are transcribed by Grok Bot; the gatekeeper only sees the marker,
    # so they always go through as "queue" and are classified after transcription.
    if item["voice_file"]:
        decision = {"action": "queue", "intent": "unklar", "urgency": 0.5, "p_injection": 0.0}
    else:
        sender_hint = f"Telegram-Nutzer @{item['from']['username']}" if item["from"]["username"] else None
        decision = gatekeeper.evaluate(item["text"], sender_hint=sender_hint)

    payload = {
        "text": item["text"],
        "voice_file": item["voice_file"],
        "intent": decision["intent"],
        "urgency": decision["urgency"],
        "action": decision["action"],
        "chat_id": item["chat_id"],
        "message_id": item["message_id"],
        "from": item["from"],
    }
    _log(decision["action"], {**payload, "decision": decision})

    status = _wake_grokbot(payload) if decision["action"] in WAKE_ACTIONS else None
    return {"ok": True, "action": decision["action"], "grokbot_status": status}
