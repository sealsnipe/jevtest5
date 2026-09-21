"""Local test for relay/app.py – no network, gatekeeper.evaluate is mocked.

    python tests/relay_test.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TMP_LOG = tempfile.mkdtemp(prefix="relay_log_")
os.environ.update({
    "TELEGRAM_WEBHOOK_SECRET": "test-secret",
    "GROKBOT_WEBHOOK_URL": "https://grokbot.example/webhook",
    "GROKBOT_WEBHOOK_KEY": "test-key",
    "RELAY_LOG_DIR": TMP_LOG,
    "CHEF_CHAT_ID": "999",
    "TELEGRAM_BOT_TOKEN": "123:test-token",
    "RELAY_API_KEY": "relay-key",
})

from fastapi.testclient import TestClient  # noqa: E402

from relay import app as relay_app  # noqa: E402

client = TestClient(relay_app.app)
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}


def tg_update(text: str | None = None, voice_id: str | None = None, chat_id: int = 1234) -> dict:
    msg = {
        "message_id": 42,
        "chat": {"id": chat_id, "type": "private"},
        "from": {"id": 1234, "username": "mueller", "first_name": "Max"},
    }
    if text is not None:
        msg["text"] = text
    if voice_id:
        msg["voice"] = {"file_id": voice_id, "duration": 3}
    return {"update_id": 1, "message": msg}


def fake_decision(action: str, intent: str = "termin", urgency: float = 0.33) -> dict:
    return {"action": action, "intent": intent, "urgency": urgency, "p_injection": 0.01,
            "p_spam": 0.02, "p_needs_action": 0.9, "intent_confidence": 0.8,
            "urgency_confidence": 0.7, "latency_ms": 1, "cost_usd": 0.0, "model": "mock"}


def log_lines(action: str) -> list[dict]:
    p = Path(TMP_LOG) / f"{action}.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]


def run() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        print(f"  {'OK ' if cond else 'FAIL'} {name}")
        failures += not cond

    print("relay_test")

    # 1. wrong secret -> 200 but unauthorized, nothing forwarded
    with mock.patch.object(relay_app.gatekeeper, "evaluate") as ev, mock.patch.object(relay_app.requests, "post") as post:
        r = client.post("/telegram", json=tg_update("Hallo"), headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
        check("bad secret: HTTP 200", r.status_code == 200)
        check("bad secret: unauthorized", r.json() == {"ok": False, "reason": "unauthorized"})
        check("bad secret: gatekeeper not called", not ev.called)
        check("bad secret: grokbot not called", not post.called)

    # 2. queue -> grokbot woken with the agreed payload
    with mock.patch.object(relay_app.gatekeeper, "evaluate", return_value=fake_decision("queue")) as ev, \
         mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 202
        r = client.post("/telegram", json=tg_update("Ich hätte gern einen Termin."), headers=HEADERS)
        check("queue: HTTP 200", r.status_code == 200)
        check("queue: action", r.json()["action"] == "queue")
        check("queue: grokbot status passed through", r.json()["grokbot_status"] == 202)
        ev.assert_called_once_with("Ich hätte gern einen Termin.", sender_hint="Telegram-Nutzer @mueller")
        args, kwargs = post.call_args
        check("queue: url", args[0] == "https://grokbot.example/webhook")
        check("queue: bearer header", kwargs["headers"] == {"Authorization": "Bearer test-key"})
        payload = kwargs["json"]
        check("queue: payload keys", set(payload) == {"text", "voice_file", "intent", "urgency", "action", "from_chef", "test", "transcribed", "chat_id", "message_id", "from"})
        check("queue: not from chef", payload["from_chef"] is False)
        check("queue: payload values", payload["text"] == "Ich hätte gern einen Termin." and payload["intent"] == "termin"
              and payload["chat_id"] == 1234 and payload["message_id"] == 42 and payload["from"]["username"] == "mueller")
        check("queue: logged", len(log_lines("queue")) == 1)

    # 3. urgent -> also woken
    with mock.patch.object(relay_app.gatekeeper, "evaluate", return_value=fake_decision("urgent", "beschwerde", 1.0)), \
         mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 200
        r = client.post("/telegram", json=tg_update("Ich kündige!"), headers=HEADERS)
        check("urgent: grokbot called", post.called and r.json()["action"] == "urgent")

    # 4. drop / log / block -> only logged, no wake-up
    for action in ("drop", "log", "block"):
        with mock.patch.object(relay_app.gatekeeper, "evaluate", return_value=fake_decision(action)), \
             mock.patch.object(relay_app.requests, "post") as post:
            r = client.post("/telegram", json=tg_update(f"msg for {action}"), headers=HEADERS)
            check(f"{action}: HTTP 200, no wake-up", r.status_code == 200 and not post.called and r.json()["grokbot_status"] is None)
            check(f"{action}: logged to log/{action}.jsonl", log_lines(action)[-1]["text"] == f"msg for {action}")

    # 5. voice note -> transcribed locally, gatekeeper runs on the transcript
    with mock.patch.object(relay_app.stt, "transcribe_telegram_voice", return_value=("Ich hätte gern einen Termin.", {"stt_ms": 1})) as tr,          mock.patch.object(relay_app.gatekeeper, "evaluate", return_value=fake_decision("queue")) as ev,          mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 200
        r = client.post("/telegram", json=tg_update(voice_id="AwACAgIAAxkBAAI"), headers=HEADERS)
        payload = post.call_args.kwargs["json"]
        check("voice: transcribed with file id", tr.call_args.args[0] == "AwACAgIAAxkBAAI")
        check("voice: gatekeeper ran on transcript", ev.called and ev.call_args.args[0] == "Ich hätte gern einen Termin.")
        check("voice: payload text + flags", payload["text"] == "Ich hätte gern einen Termin." and payload["transcribed"] is True and payload["voice_file"] == "AwACAgIAAxkBAAI")

    # 5a. STT fails -> falls back to voice_pending, Grok Bot transcribes
    with mock.patch.object(relay_app.stt, "transcribe_telegram_voice", side_effect=RuntimeError("boom")),          mock.patch.object(relay_app.gatekeeper, "evaluate") as ev, mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 200
        client.post("/telegram", json=tg_update(voice_id="V2"), headers=HEADERS)
        payload = post.call_args.kwargs["json"]
        check("voice fallback: voice_pending, no gatekeeper", payload["text"] == "voice_pending" and not ev.called and payload["transcribed"] is False)

    # 5b. text from the boss -> from_chef, forwarded as queue without gatekeeper
    with mock.patch.object(relay_app.gatekeeper, "evaluate") as ev, mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 200
        r = client.post("/telegram", json=tg_update("ja", chat_id=999), headers=HEADERS)
        payload = post.call_args.kwargs["json"]
        check("chef: gatekeeper skipped", not ev.called)
        check("chef: from_chef + queue, forwarded", payload["from_chef"] is True and payload["action"] == "queue" and payload["text"] == "ja")
        check("chef: logged to chef.jsonl", log_lines("chef")[-1]["chat_id"] == 999)

    # 5c. voice note from the boss with "Testnachricht" -> transcribed, prefix stripped, customer path
    with mock.patch.object(relay_app.stt, "transcribe_telegram_voice", return_value=("Testnachricht Hallo hier Werum, Rechnung bitte.", {})),          mock.patch.object(relay_app.gatekeeper, "evaluate", return_value=fake_decision("queue", "dokument")) as ev,          mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 200
        client.post("/telegram", json=tg_update(voice_id="VOICE1", chat_id=999), headers=HEADERS)
        payload = post.call_args.kwargs["json"]
        check("chef voice test: prefix stripped, customer path", payload["test"] is True and payload["from_chef"] is False
              and ev.call_args.args[0] == "Hallo hier Werum, Rechnung bitte." and payload["intent"] == "dokument")

    # 5d. boss plays customer: "Testnachricht: ..." -> gatekeeper runs, from_chef false, test true
    with mock.patch.object(relay_app.gatekeeper, "evaluate", return_value=fake_decision("queue")) as ev,          mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 200
        client.post("/telegram", json=tg_update("Testnachricht: Hallo, ich hätte gern einen Termin.", chat_id=999), headers=HEADERS)
        payload = post.call_args.kwargs["json"]
        check("test: prefix stripped, gatekeeper ran", ev.called and ev.call_args.args[0] == "Hallo, ich hätte gern einen Termin.")
        check("test: flags", payload["test"] is True and payload["from_chef"] is False and payload["text"] == "Hallo, ich hätte gern einen Termin.")
    with mock.patch.object(relay_app.gatekeeper, "evaluate") as ev, mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.status_code = 200
        client.post("/telegram", json=tg_update("Test", chat_id=999), headers=HEADERS)
        check("test: bare 'Test' stays a chef message", not ev.called and post.call_args.kwargs["json"]["from_chef"] is True)

    # 7. /reply: voice ok -> TTS + sendVoice; voice not ok -> sendMessage + hints; bad key -> unauthorized
    RH = {"Authorization": "Bearer relay-key"}
    ok_check = {"ok": True, "hints": [], "p_natural": 0.9, "p_one_topic": 0.9, "p_filler": 0.1}
    bad_check = {"ok": False, "hints": ["zu lang: 60 Wörter, maximal 35"], "p_natural": 0.3, "p_one_topic": 0.5, "p_filler": 0.8}
    tmp_ogg = Path(TMP_LOG) / "reply.ogg"; tmp_ogg.write_bytes(b"OggS")
    with mock.patch.object(relay_app.voice_check, "evaluate", return_value=ok_check), \
         mock.patch.object(relay_app.tts, "synthesize_ogg", return_value=(tmp_ogg, {"tts_ms": 5, "duration_s": 3.2})) as syn, \
         mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.json.return_value = {"ok": True, "result": {"message_id": 77}}
        r = client.post("/reply", json={"chat_id": 1234, "text": "Dienstag um zehn passt. Sehen wir uns?", "reply_to_message_id": 42}, headers=RH)
        check("reply voice: sent as voice", r.json()["ok"] and r.json()["sent_as"] == "voice" and r.json()["message_id"] == 77)
        check("reply voice: sendVoice called with file", "sendVoice" in post.call_args.args[0] and "voice" in post.call_args.kwargs["files"])
        check("reply voice: synthesized the text", syn.call_args.args[0] == "Dienstag um zehn passt. Sehen wir uns?")
    with mock.patch.object(relay_app.voice_check, "evaluate", return_value=bad_check), \
         mock.patch.object(relay_app.tts, "synthesize_ogg") as syn, mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.json.return_value = {"ok": True, "result": {"message_id": 78}}
        r = client.post("/reply", json={"chat_id": 1234, "text": "viel zu langer Text"}, headers=RH)
        check("reply voice fails check: sent as text with hints", r.json()["sent_as"] == "text" and r.json()["voice_check"]["hints"] and not syn.called and "sendMessage" in post.call_args.args[0])
    with mock.patch.object(relay_app.requests, "post") as post:
        post.return_value.json.return_value = {"ok": True, "result": {"message_id": 79}}
        r = client.post("/reply", json={"chat_id": 1234, "text": "Hallo", "mode": "text"}, headers=RH)
        check("reply text mode: no voice check", r.json()["sent_as"] == "text" and r.json()["voice_check"] is None)
    with mock.patch.object(relay_app.requests, "post") as post:
        r = client.post("/reply", json={"chat_id": 1234, "text": "Hallo"}, headers={"Authorization": "Bearer wrong"})
        check("reply: bad key rejected", r.json() == {"ok": False, "reason": "unauthorized"} and not post.called)

    # 6. update without message (e.g. sticker, channel post) -> ignored
    with mock.patch.object(relay_app.gatekeeper, "evaluate") as ev:
        r = client.post("/telegram", json={"update_id": 2, "message": {"message_id": 1, "chat": {"id": 1}, "sticker": {}}}, headers=HEADERS)
        check("sticker: ignored", r.json()["action"] == "ignored" and not ev.called)

    print(f"\n{'ALLE TESTS OK' if not failures else f'{failures} FEHLER'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
