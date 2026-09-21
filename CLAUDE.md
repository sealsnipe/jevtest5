# Projekt Sekretärin – KI-Sekretärin mit Grok Bot + Jev

Stand: 2026-09-21. Sprache im Projekt: Deutsch (Code-Kommentare/Bezeichner Englisch).

## Ziel

Eine KI-Sekretärin, die über Telegram erreichbar ist (Text + Sprachnachrichten, später
Live-Voice), Anfragen entgegennimmt, Termine/Rückrufe/Mails/Tabellen erledigt und
nur bei Bedarf den Chef (Sealsnipe) einbindet. Vorbild: TeslaTobi-Livestream
"Wir bauen eine KI-Sekretärin mit Grok Bot – inkl. Telefondienst und Tabellenkalkulation".

Zwei Grundsätze:

1. **Grok Bot baut und betreibt sich selbst.** Grok Bot ist der Assistent, über den weitere
   Assistenten (Sub-Bots) gebaut werden. Alles, was per Nachricht/Skill/Routine in Grok Bot
   einrichtbar ist, wird dort eingerichtet – nicht hier nachgebaut.
2. **Jev (TypeSafe) liefert die Entscheidungs-Layer.** Jev ist kein Chat-Modell; es gibt
   typisierte Antworten mit kalibrierter Wahrscheinlichkeit zurück. Wir bauen die Layer
   hier als kleine, testbare Python-Module und sagen Grok Bot dann, wie er sie nutzt.

## Architektur (Zielbild)

```
Telegram-User
   │  Text / Voice Note
   ▼
Relay (relay/)  ── Jev Layer 1 "Türsteher"  ──► Grok-Bot-Webhook (Routine-Trigger)
   │                (spam? wecken? dringlich? angriff?)
   ▼
Grok Bot "Empfang"  ── STT (Parakeet v3 lokal ODER Grok STT) ──► Text
   ▼
Grok Bot "Sekretärin" (Sub-Bot)  ── Mail / Excel / Docx / Kalender via Connectors
   │  Entwurf
   ▼
Jev Layer 2 "Autonomie-Regler" ──► senden  |  Freigabe an Chef
```

## Jev-Layer (Reihenfolge der Umsetzung)

| # | Layer | Modul | Status |
|---|-------|-------|--------|
| 0 | Basistest: funktioniert Jev via OpenRouter auf Deutsch? | `tests/jev_smoke_test.py` | **jetzt** |
| 1 | Türsteher / Spamfilter (spam, wecken, dringlichkeit, intent) | `layers/gatekeeper.py` | nach Test 0 |
| 2 | Autonomie-Regler (Entwurf freigeben oder eskalieren) | `layers/autonomy_gate.py` | offen |
| 3 | Injection-Firewall (instruiert die Nachricht den Bot? Chef-Impersonation?) | `layers/firewall.py` | offen |
| 4 | Vollständigkeits-Check (Name, Termin, Rückrufnummer vorhanden?) | `layers/completeness.py` | offen |
| 5 | QA-Spalte für Excel (erledigt? Ton? Zufriedenheit?) | `layers/qa.py` | offen |

Regel: Jede Layer ist eine Funktion `evaluate(state: str, ...) -> dict` mit festen
Schwellwerten in Code, nicht im Prompt. Schwellwerte in `layers/config.py`.

## Jev via OpenRouter – Fakten (verifiziert 2026-09-21)

- Endpoint: `POST https://openrouter.ai/api/v1/systemone` (eigener Endpoint, NICHT chat/completions)
- Auth: `Authorization: Bearer $OPENROUTER_API_KEY`
- Modelle: `typesafe/jev-1.13` (gepinnt, bevorzugt) · `~typesafe/jev-latest` (Alias, wandert)
- Preis: $0.042 / M Input-Tokens, Output kostenlos, 32K Kontext
- Request: `{"model", "state", "questions": {<id>: {...}}}`
- Fragetypen:
  - `noul`: `{"type":"noul","instructions":"..."}` → `{"noul": 0.0-1.0}` (Ja-Wahrscheinlichkeit)
  - `choice`: `{"type":"choice","instructions":"...","criteria":{"opt":"Beschreibung",...}}`
    → `{"choice":"opt","confidence":0-1,"probabilities":{...}}` (bis 255 Optionen)
  - `score`: `{"type":"score","instructions":"...","criteria":["Level0","Level1",...]}`
    → `{"score":float,"confidence":0-1,"probabilities":{"0":..},"legend":{...}}` (2–10 Level)
- Response zusätzlich: `id`, `provider`, `model` (gepinnte Version), `usage.cost`
- Alle Fragen eines Requests werden parallel beantwortet → immer bündeln, nie einzeln.
- SDK optional: `pip install typesafe-sdk`, dann `TYPESAFE_BASE_URL=https://openrouter.ai/api`
  und `TYPESAFE_API_KEY=<OpenRouter-Key>`. `client.models.list()` schlägt via OpenRouter fehl (egal).

Best Practices (aus TypeSafe-Docs):
- Level/Optionen als **Situationen** beschreiben, nicht als Grade ("moderat" bringt nichts).
- Eine Frage = eine Dimension. Mehrere Dimensionen = mehrere Fragen, in Code kombinieren.
- Bei `choice` immer eine `other`/`none`-Option anbieten.
- Beispiele in Kriterien (`{"what":..., "examples":[...]}`) nur, wenn sie wie echte Inputs aussehen.
- Version pinnen sobald Schwellwerte getunt sind; `response.model` loggen.

## Grok Bot – Fakten (verifiziert 2026-09-21)

- Cloud-Computer pro Account (Browser, Dateisystem, Terminal). Alle Bots teilen Dateien,
  Browser-Sessions, Credentials. Bots sind KEINE Sicherheitsgrenze.
- Dauerhafte Dateien nach `/workspace`; manuell installierte Pakete gelten als ersetzbar
  → Install-Skripte als Skill ablegen.
- Connectors = Plugins aus Marketplace (`@` im Chat). Skills per `/`. Routinen: Zeitplan,
  Slack/GitHub/Teams/Linear/Sentry/PagerDuty-Events **und Webhook** (URL + Bearer-Key beim
  Anlegen der Routine unter "Add trigger → Webhook").
- Telegram-Anbindung: über Composio (Bot-API-Modus). Ein eigenes `grokbot-telegram`-Plugin gibt es im Marketplace nicht (geprüft 2026-09-21).
- Kontingent: wöchentlich, zählt Agent-Schritte + Tokens. Schwärme laufen schnell leer.
  → 2–3 Bots reichen: "Empfang", "Sekretärin", optional "Chef/Koordination".
- Voice: Grok Voice Agent API (Realtime, WebSocket, OpenAI-Realtime-kompatibel), STT 25 Sprachen.
  Telegram-Bots können keine Calls → Voice Notes (jetzt) / Mini App mit Live-Voice (später).

## Offene Punkte

- Telegram → Grok-Bot-Webhook braucht Bearer-Header; Telegram schickt nur eigenen Secret-Header
  → kleines Relay nötig (relay/), alternativ Hookdeck.
- Jev auf Deutsch: nicht belegt, wird mit Test 0 geprüft.
- Parakeet v3 (HandyTTS) als lokales STT auf dem Grok-Bot-Computer: Installation als Skill.
- DSGVO: Jev/OpenRouter/xAI sind Auftragsverarbeiter. Für echte Kundendaten AV-Verträge.

## Konventionen

- Python 3.11+, nur `requests` als Abhängigkeit für die Layer (kein SDK-Zwang).
- API-Key NUR aus Umgebungsvariable `OPENROUTER_API_KEY`. Nie in Dateien, nie im Chat.
- Jede Layer hat eine Testdatei in `tests/` mit deutschen Beispielnachrichten und
  erwarteten Ergebnissen (`expected`), damit Änderungen an Prompts/Schwellwerten messbar sind.
- `grokbot/RUNBOOK.md` enthält die Nachrichten, die 1:1 an Grok Bot gehen.

## Nächste Schritte

1. `python tests/jev_smoke_test.py` ausführen (braucht `OPENROUTER_API_KEY`).
2. Ergebnis bewerten: Trefferquote, Latenz, Kosten. Bei < 8/10 Treffern Kriterien nachschärfen.
3. Layer 1 `layers/gatekeeper.py` finalisieren, dann `grokbot/RUNBOOK.md` Schritt 1–3 an Grok Bot geben.
