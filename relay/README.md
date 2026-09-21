# Relay: Telegram-Webhook → Jev-Türsteher → Grok-Bot-Webhook

Telegram schickt nur seinen eigenen Secret-Header, der Grok-Bot-Webhook braucht
`Authorization: Bearer <key>`. `app.py` sitzt dazwischen und lässt zusätzlich Layer 1+3
(`layers.gatekeeper`) laufen, damit Grok Bot nur bei echten Anfragen geweckt wird.

## Betrieb (Stand 2026-09-22)

- **Empfang per Long Polling** (Default, wie OpenClaw): das Relay ruft `getUpdates` selbst auf. Kein Webhook,
  kein Tunnel, keine DNS-Wartezeit. Latenz 0,5–2 s. `RELAY_MODE=webhook` schaltet auf `POST /telegram` um.
- **Tunnel nur für den Rückkanal** `POST /reply` (Grok Bot → Relay). Die aktuelle URL steht in jedem Payload
  (`relay_url`) und in `log/relay_url.txt`.
- **Supervisor** `relay/supervisor.py`: hält Relay + Tunnel am Leben, meldet Neustarts per Telegram an den Chef.
- **Doctor** `relay/doctor.py`: alle 10 min lokal / Tunnel / Polling-Heartbeat / Telegram prüfen, Alarm mit 1 h Cooldown.
- Beide als Windows-Aufgaben: `powershell -File relay/install_tasks.ps1` (Sekretaerin Relay bei Anmeldung,
  Sekretaerin Doctor alle 10 min). Kinderprozesse ohne Konsolenfenster.

## Ablauf

1. Update kommt per Polling (oder `POST /telegram` mit Secret-Header im Webhook-Modus).
2. Text aus `message.text`; bei `message.voice` wird `text = "voice_pending"` und `voice_file = <file_id>`
   gesetzt (Transkription macht Grok Bot, Türsteher wird übersprungen, action `queue`).
3. `gatekeeper.evaluate(text, sender_hint=...)` → action `block | drop | log | queue | urgent`.
4. `queue`/`urgent` → `POST GROKBOT_WEBHOOK_URL` mit Bearer-Key und Payload:
   ```json
   {"text": "...", "voice_file": null, "intent": "termin", "urgency": 0.33, "action": "queue",
    "from_chef": false, "test": false, "chat_id": 1234, "message_id": 42,
    "from": {"id": 1234, "username": "mueller", "first_name": "Max", "last_name": null}}
   ```
   `from_chef`: Nachricht aus `CHEF_CHAT_ID` (Türsteher übersprungen, action immer `queue`; ob es eine
   Freigabe ist, entscheidet die Sekretärin). `test`: Chef-Nachricht begann mit "Test"/"Testnachricht",
   Präfix entfernt, wird wie ein Kunde behandelt. Für andere Chats ist das Wort wirkungslos.
5. Jede Entscheidung landet in `log/<action>.jsonl`. `drop`/`log`/`block` wecken Grok Bot nicht.
6. Antwort an Telegram ist immer HTTP 200 (sonst retried Telegram das Update).

## Rückkanal: `POST /reply` (Grok Bot → Relay → Telegram)

Header `Authorization: Bearer <RELAY_API_KEY>`, Body
`{"chat_id", "text", "reply_to_message_id"?, "mode": "voice"|"text", "force"?: false}`.

- `mode: voice`: erst `layers.voice_check` (Regeln aus docs/voice_rules.md). Bestanden → Piper-TTS lokal
  (`relay/tts.py`, de_DE-thorsten-medium) → OGG/Opus → `sendVoice`. Nicht bestanden → `sendMessage` als
  Text, Antwort enthält `voice_check.hints`. `force: true` erzwingt Sprache.
- `mode: text`: `sendMessage`.
- Antwort: `{"ok", "sent_as", "message_id", "voice_check", "tts_ms", "duration_s"}`; Log in `log/reply.jsonl`.

Der Bot-Token bleibt damit ausschließlich im Relay. Grok Bot bekam ihn über die Secret-Karte nie in die Shell
(nur Anzeigename, keine Env-Injektion), und der Composio-Connector hat kein `sendVoice`.

Sprachnachrichten **rein** transkribiert das Relay ebenfalls lokal (`relay/stt.py`, Parakeet v3), siehe
docs/stt_setup.md.

## Starten

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# .env aus .env.example anlegen und füllen
uvicorn relay.app:app --host 0.0.0.0 --port 8080
```

Öffentlich erreichbar machen (z. B. Cloudflare Tunnel oder ngrok), dann Webhook setzen:

```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<relay-host>/telegram&secret_token=<TELEGRAM_WEBHOOK_SECRET>
```

## Test ohne Netz

```powershell
python tests\relay_test.py
```

Alternative ohne eigenen Code: Hookdeck Event Gateway vor den Grok-Bot-Webhook (dann ohne Türsteher).
