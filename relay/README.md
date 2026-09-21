# Relay (noch nicht gebaut)

Aufgabe: Telegram-Webhook (Bot-API, Secret-Header `X-Telegram-Bot-Api-Secret-Token`)
entgegennehmen, Layer 1 (`layers.gatekeeper`) ausführen und nur bei action ∈ {queue, urgent}
den Grok-Bot-Webhook mit `Authorization: Bearer <key>` aufrufen.

Wird nach erfolgreichem Test 0 und Runbook Schritt 6 gebaut (FastAPI, ~80 Zeilen).
Alternative ohne eigenen Code: Hookdeck Event Gateway vor den Grok-Bot-Webhook.
