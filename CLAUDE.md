# Projekt Sekretärin – KI-Sekretärin mit Grok Bot + Jev

Stand: 2026-09-22. Sprache im Projekt: Deutsch (Code-Kommentare/Bezeichner Englisch).

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
Relay (relay/)  ── STT Parakeet v3 lokal ── Jev "Türsteher"+"Firewall" ──► Grok-Bot-Webhook
   │  (Text; Voice → Text auf dem PC)        (spam? wecken? dringlich? angriff?)   (Routine "Empfang")
   ▼
Grok Bot "Empfang"  ──► Grok Bot "Sekretärin"  ── Excel (openpyxl) / Gmail / Calendar via Connectors
   │                        │  Jev: Vorgangs-Zuordnung, Autonomie-Regler, Chef-Antwort, Aktions-Gate
   │                        ▼
   │                   POST <Relay>/reply  ── Jev Voice-Check ── Piper-TTS lokal ──► Telegram sendVoice/sendMessage
   ▼
Freigabe an Chef per Telegram (from_chef) nur bei Aktion/"review"; Dashboard: dashboard/ (Port 8095)
```

## Jev-Layer (Reihenfolge der Umsetzung)

| # | Layer | Modul | Status |
|---|-------|-------|--------|
| 0 | Basistest: funktioniert Jev via OpenRouter auf Deutsch? | `tests/jev_smoke_test.py` | 14/14 |
| 1 | Türsteher / Spamfilter (spam, wecken, dringlichkeit, intent) | `layers/gatekeeper.py` | live (Relay + Grok-Bot-Skill) |
| 2 | Autonomie-Regler (Entwurf freigeben oder eskalieren) | `layers/autonomy_gate.py` | 8/8, noch nicht bei Grok Bot. Offen: Faktenaussagen-Frage |
| 3 | Injection-Firewall | in `gatekeeper.py` (Frage `injection`) | live |
| 4 | Vollständigkeits-Check (Name, Termin, Rückrufnummer vorhanden?) | `layers/completeness.py` | offen, Grok macht es bisher selbst |
| 5 | QA-Spalte für Excel (erledigt? Ton? Zufriedenheit?) | `layers/qa.py` | offen |
| 6 | Aktions-Gate (Dateiaktion → execute/ask/refuse) | `layers/action_gate.py` | 9/9, noch nicht bei Grok Bot |
| – | Chef-Antwort einordnen (freigabe/ablehnung/aenderung/anweisung/rueckfrage) | `layers/chef_reply.py` | 10/10 |
| – | Vorgangs-Zuordnung (Nachricht → offener Vorgang oder neu) | `layers/matcher.py` | 6/6 |
| – | Transkript-Check (Sprachnachricht brauchbar?) | `layers/transcript_check.py` | 6/6 |
| – | Voice-Check (Antworttext als TTS-Sprachnachricht tauglich?) | `layers/voice_check.py` + `docs/voice_rules.md` | 10/10 |

Test/Showcase für alles außer Türsteher: `python tests/layers_showcase.py [autonomy|chef|match|transcript|action|voice]`.

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
- **Unsicherheit eskalieren, nicht wegrunden.** Nur die Frage prüfen, die die Entscheidung trägt.
  noul nahe 0.5 oder Score-Masse jenseits der Schwelle ≥ 0.40 → eine Stufe eskalieren (drop/log →
  queue, send → review, execute → ask), Grok Bot schaut dann drauf. Konfidenz-Feld bei Scores ist
  kein brauchbares Signal. Details docs/testlog.md.

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
  Telegram-**Bots** können keine Calls. Echte Telegram-Anrufe gehen nur über einen **User-Account**
  (MTProto: Telethon/Pyrogram + py-tgcalls), Beispiel `telegram-call-mcp`. Alternativ Mini App mit
  Live-Voice. Aktuell: Voice Notes rein (STT) und raus (TTS nach docs/voice_rules.md).

## Offene Punkte

- Relay empfängt per **Long Polling** (wie OpenClaw): Quick-Tunnel-Hostnamen brauchten bei Telegram 5+ min bis
  zur DNS-Auflösung, Webhook nach jedem Neustart kaputt. Tunnel nur noch für `/reply`. Supervisor + Doctor als
  Windows-Aufgaben (relay/install_tasks.ps1). Details relay/README.md.
- Relay (relay/app.py) ist gebaut und getestet (2026-09-21): Relay → Jev → Grok-Bot-Webhook antwortet 200.
  Webhook-URL liegt auf `api2.cursor.sh/automations/webhook/<id>`, Key `crsr_…` (Grok Bot läuft auf
  Cursor-Infrastruktur). URL+Key nur im Routinen-Panel sichtbar, der Bot selbst kann sie nicht auslesen.
  Tunnel/Webhook erledigt (siehe oben).
- Jev auf Deutsch: nicht belegt, wird mit Test 0 geprüft.
- STT (Parakeet v3, GPU 0,44 s/12 s) und TTS (Piper de_DE-thorsten, 0,24 s/4,5 s) laufen lokal im Relay,
  siehe docs/stt_setup.md und relay/README.md (`POST /reply`). Bot-Token nur im Relay.
  Grok Bot bekommt fertigen Text (`transcribed: true`). Grok Bot hatte vorher eigenmächtig Gemini über
  OpenRouter genutzt: Key ist nur für Jev, steht jetzt in der Empfang-Routine.
- Grok Bot hat Lesezugriff auf den lokalen PC (hat Dateien direkt aus `W:\` gelesen). Den
  „erlaubten Bereich" in den Grok-Bot-Einstellungen auf den Projektordner beschränken. Jev-Aktions-Gate
  ist Berater, keine Sperre.
  **Befund 2026-09-22:** Bot meldete „W: darf ich nicht direkt lesen", kopierte die Dateien dann über
  `C:\Users\Matthias\Downloads` als Staging. Die Sperre ist keine harte Grenze, der Bot umgeht sie
  selbstständig. Staging enthielt nur die 10 angeforderten Dateien, wurde gelöscht.
- DSGVO: Jev/OpenRouter/xAI sind Auftragsverarbeiter. Für echte Kundendaten AV-Verträge.

## Konventionen

- Python 3.11+, nur `requests` als Abhängigkeit für die Layer (kein SDK-Zwang).
- API-Key NUR aus Umgebungsvariable `OPENROUTER_API_KEY`. Nie in Dateien, nie im Chat.
- Jede Layer hat eine Testdatei in `tests/` mit deutschen Beispielnachrichten und
  erwarteten Ergebnissen (`expected`), damit Änderungen an Prompts/Schwellwerten messbar sind.
- `grokbot/RUNBOOK.md` enthält die Nachrichten, die 1:1 an Grok Bot gehen.

## Nächste Schritte

1. Frauenstimme: Chatterbox Multilingual (lokal, MIT) oder xAI-TTS (Cloud) als zweite Engine in `relay/tts.py`.
2. Feste Relay-Adresse (ngrok-Subdomain oder Cloudflare-Tunnel mit Domain) statt Quick-Tunnel.
3. Layer 2: eigene Frage „enthält Sachangaben, die nicht aus der Anfrage stammen" (siehe testlog).
4. Layer 4 Vollständigkeit, Layer 5 QA-Spalte.
5. Jev-Browser-Navigation für Grok Bot (Elementtabelle + choice), siehe jev-browser-skill-demo.
6. Relay auf einen kleinen Server (Pi/VPS) statt Arbeits-PC, sobald echte Kunden schreiben.
