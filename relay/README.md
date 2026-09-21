# Relay: Telegram-Webhook → Jev-Türsteher → Grok-Bot-Webhook

Telegram schickt nur seinen eigenen Secret-Header, der Grok-Bot-Webhook braucht
`Authorization: Bearer <key>`. `app.py` sitzt dazwischen und lässt zusätzlich Layer 1+3
(`layers.gatekeeper`) laufen, damit Grok Bot nur bei echten Anfragen geweckt wird.

## Ablauf

1. `POST /telegram` – Header `X-Telegram-Bot-Api-Secret-Token` muss `TELEGRAM_WEBHOOK_SECRET` entsprechen.
2. Text aus `message.text`; bei `message.voice` wird `text = "voice_pending"` und `voice_file = <file_id>`
   gesetzt (Transkription macht Grok Bot, Türsteher wird übersprungen, action `queue`).
3. `gatekeeper.evaluate(text, sender_hint=...)` → action `block | drop | log | queue | urgent`.
4. `queue`/`urgent` → `POST GROKBOT_WEBHOOK_URL` mit Bearer-Key und Payload:
   ```json
   {"text": "...", "voice_file": null, "intent": "termin", "urgency": 0.33, "action": "queue",
    "chat_id": 1234, "message_id": 42,
    "from": {"id": 1234, "username": "mueller", "first_name": "Max", "last_name": null}}
   ```
5. Jede Entscheidung landet in `log/<action>.jsonl`. `drop`/`log`/`block` wecken Grok Bot nicht.
6. Antwort an Telegram ist immer HTTP 200 (sonst retried Telegram das Update).

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
