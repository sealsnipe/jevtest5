"""Relay: Telegram Bot-API webhook -> Jev gatekeeper -> Grok Bot webhook.

Telegram can only send its own secret header, Grok Bot's webhook trigger needs
`Authorization: Bearer <key>`. This tiny service sits in between and additionally
runs Layer 1+3 (gatekeeper) so Grok Bot is only woken for real requests.

    uvicorn relay.app:app --host 0.0.0.0 --port 8080

Environment (see .env.example): TELEGRAM_WEBHOOK_SECRET, GROKBOT_WEBHOOK_URL,
GROKBOT_WEBHOOK_KEY, OPENROUTER_API_KEY, CHEF_CHAT_ID. Loaded from .env if present.

Actions in the payload: queue | urgent (from the gatekeeper). Messages from CHEF_CHAT_ID
carry `from_chef: true`, skip the gatekeeper and are always forwarded (as queue), voice
notes included; whether it is an approval is decided by the secretary bot, who knows
if a draft is waiting.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header, Request
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from layers import gatekeeper, voice_check  # noqa: E402
from relay import stt, tts  # noqa: E402

LOG_DIR = Path(os.environ.get("RELAY_LOG_DIR", Path(__file__).resolve().parent.parent / "log"))
URL_FILE = Path(__file__).resolve().parent.parent / "log" / "relay_url.txt"   # written by relay/supervisor.py


def _public_url() -> str | None:
    """Current tunnel URL, sent along in every payload so the secretary bot always
    knows where POST /reply lives, even after a tunnel restart."""
    try:
        return URL_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return os.environ.get("RELAY_PUBLIC_URL")
WAKE_ACTIONS = {"queue", "urgent"}
VOICE_PENDING = "voice_pending"
# Boss plays a customer: "Test: ..." / "Testnachricht ..." at the start -> treated like a
# normal sender, gatekeeper runs, payload gets test=true. For voice notes the Empfang routine
# applies the same rule after transcription.
TEST_PREFIX = re.compile(r"^\W*test(nachricht|kunde)?(?![a-zäöü])[\s:,.\-]*", re.I)

app = FastAPI(title="Projekt Sekretärin – Relay")

STT_ENABLED = bool(os.environ.get("TELEGRAM_BOT_TOKEN")) and os.environ.get("RELAY_STT", "1") != "0"


@app.on_event("startup")
def _warmup() -> None:
    if STT_ENABLED:
        try:
            ms = stt.warmup()
            _log("info", {"event": "stt_warmup", "model": stt.MODEL_NAME, "load_ms": ms})
        except Exception as e:  # noqa: BLE001
            _log("error", {"reason": f"stt warmup: {e}"})
    if os.environ.get("RELAY_API_KEY"):
        try:
            ms = tts.warmup()
            _log("info", {"event": "tts_warmup", "load_ms": ms})
        except Exception as e:  # noqa: BLE001
            _log("error", {"reason": f"tts warmup: {e}"})


# --- Outbound: Grok Bot -> Relay -> Telegram (text or local-TTS voice note) ------------

class Reply(BaseModel):
    chat_id: int
    text: str
    reply_to_message_id: int | None = None
    mode: str = "voice"          # "voice" | "text"
    force: bool = False          # send as voice even if voice_check says no


def _tg(method: str, **kwargs: Any) -> dict[str, Any]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nicht gesetzt")
    files = kwargs.pop("files", None)
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", data=kwargs, files=files, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"{method}: {data.get('description')}")
    return data["result"]


@app.post("/reply")
def reply(body: Reply, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Send a reply to a Telegram chat on behalf of the secretary bot. mode=voice runs
    layers.voice_check first; if the text breaks the voice rules it is sent as text and
    the hints are returned so the bot can shorten and retry."""
    key = os.environ.get("RELAY_API_KEY")
    if not key or authorization != f"Bearer {key}":
        return {"ok": False, "reason": "unauthorized"}

    sent_as = "text"
    check: dict[str, Any] | None = None
    meta: dict[str, Any] = {}
    try:
        if body.mode == "voice":
            check = voice_check.evaluate(body.text)
            if check["ok"] or body.force:
                ogg, meta = tts.synthesize_ogg(body.text)
                try:
                    with ogg.open("rb") as fh:
                        res = _tg("sendVoice", chat_id=body.chat_id, reply_to_message_id=body.reply_to_message_id or "",
                                  files={"voice": ("reply.ogg", fh, "audio/ogg")})
                finally:
                    ogg.unlink(missing_ok=True)
                sent_as = "voice"
            else:
                res = _tg("sendMessage", chat_id=body.chat_id, text=body.text, reply_to_message_id=body.reply_to_message_id or "")
        else:
            res = _tg("sendMessage", chat_id=body.chat_id, text=body.text, reply_to_message_id=body.reply_to_message_id or "")
    except Exception as e:  # noqa: BLE001
        _log("error", {"reason": f"reply: {e}", "chat_id": body.chat_id, "text": body.text[:200]})
        return {"ok": False, "reason": str(e), "voice_check": check}

    out = {"ok": True, "sent_as": sent_as, "message_id": res.get("message_id"),
           "voice_check": {k: check[k] for k in ("ok", "hints")} if check else None, **meta}
    _log("reply", {"chat_id": body.chat_id, "text": body.text, "sent_as": sent_as, "mode": body.mode,
                   "voice_check": check, **meta})
    return out


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

    # Messages from the boss always go through, no gatekeeper (approvals must not be "log"ged away).
    chef_id = os.environ.get("CHEF_CHAT_ID")
    from_chef = bool(chef_id) and str(item["chat_id"]) == chef_id
    # Voice note: transcribe locally (Parakeet v3) so the gatekeeper can run on text and
    # Grok Bot receives plain text. Audio never leaves this machine.
    stt_meta: dict[str, Any] | None = None
    if item["voice_file"] and STT_ENABLED:
        try:
            item["text"], stt_meta = stt.transcribe_telegram_voice(item["voice_file"])
            item["transcribed"] = True
        except Exception as e:  # noqa: BLE001
            _log("error", {"reason": f"stt: {e}", "voice_file": item["voice_file"]})
    if item.get("transcribed") and not item["text"]:
        return {"ok": True, "action": "ignored", "reason": "leeres Transkript"}

    is_test = False
    if from_chef and item["text"] != VOICE_PENDING:
        m = TEST_PREFIX.match(item["text"])
        if m and len(item["text"]) > m.end():
            is_test, from_chef = True, False
            item["text"] = item["text"][m.end():]
    if from_chef:
        decision = {"action": "queue", "intent": "unklar", "urgency": 0.5, "p_injection": 0.0}
    # Voice note without local STT: Grok Bot transcribes, gatekeeper runs there afterwards.
    elif item["text"] == VOICE_PENDING:
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
        "from_chef": from_chef,
        "test": is_test,
        "transcribed": bool(item.get("transcribed")),
        "relay_url": _public_url(),
        "chat_id": item["chat_id"],
        "message_id": item["message_id"],
        "from": item["from"],
    }
    _log("chef" if from_chef else decision["action"], {**payload, "decision": decision, "stt": stt_meta})

    status = _wake_grokbot(payload) if decision["action"] in WAKE_ACTIONS else None
    return {"ok": True, "action": decision["action"], "grokbot_status": status}
