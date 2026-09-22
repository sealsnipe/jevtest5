# Projekt Sekretärin

KI-Sekretärin auf Basis von Grok Bot (xAI) mit Jev-Entscheidungslayern (TypeSafe via OpenRouter),
erreichbar über Telegram mit Text und Sprachnachrichten. Transkription und Stimme laufen lokal.

**Komplette Anleitung mit allen Grok-Bot-Prompts: [docs/SETUP.md](docs/SETUP.md).**
**Was bei Grok Bot funktionierte und was nicht: [docs/grokbot_erfahrungen.md](docs/grokbot_erfahrungen.md).**
Projektkontext: `CLAUDE.md`. Entstehungsprotokoll: `grokbot/RUNBOOK.md`. Messwerte: `docs/testlog.md`.

Aus einem frischen Clone getestet (2026-09-22): Installation nach SETUP.md, Smoke-Test 14/14, Showcase 49/49,
lokale Stimme und Transkription. Repo in einen Pfad ohne Umlaute klonen.

## Schnellstart (Test 0)

```powershell
cd "W:\Coding\Grokbot\Projekt Sekretärin"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OPENROUTER_API_KEY = "sk-or-..."      # nur für diese Shell-Sitzung
python tests\jev_smoke_test.py
```

Einzelne Nachricht testen:

```powershell
python -m layers.gatekeeper "Hallo, ich hätte gern einen Termin nächste Woche."
```

Relay lokal testen (ohne Netz) und starten: siehe `relay/README.md`.

## Dashboard (alle Jev-Entscheidungen)

Jede Layer-Auswertung landet in `log/jev_decisions.jsonl` (State, Jev-Antworten, Entscheidung, Latenz, Kosten).

```powershell
.\.venv\Scripts\python -m uvicorn dashboard.app:app --port 8095
```

Dann http://127.0.0.1:8095 öffnen. Kacheln, Verteilung je Layer und Ergebnis, Verlauf mit Filter;
Klick auf eine Zeile zeigt, was Jev gesehen hat, die Wahrscheinlichkeiten je Frage und die Code-Entscheidung.
Nur lokal, nicht durch den Tunnel. Daten erzeugen: `python tests/layers_showcase.py` und `python tests/jev_smoke_test.py`.


## Struktur

```
CLAUDE.md            Projektkontext für Claude Code
layers/              Jev-Layer (jev_client, gatekeeper, config, …)
tests/               Tests mit deutschen Beispielnachrichten
relay/               Telegram-Webhook → Türsteher → Grok-Bot-Webhook (FastAPI, relay/app.py)
grokbot/RUNBOOK.md   Nachrichten, die 1:1 an Grok Bot gehen
dashboard/           Lokales Dashboard für log/jev_decisions.jsonl (Port 8095)
docs/                Notizen, Recherche, testlog.md, voice_rules.md
```
