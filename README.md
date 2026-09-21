# Projekt Sekretärin

KI-Sekretärin auf Basis von Grok Bot (xAI) mit Jev-Entscheidungslayern (TypeSafe via OpenRouter).
Projektkontext und Fakten: siehe `CLAUDE.md`. Anweisungen an Grok Bot: `grokbot/RUNBOOK.md`.

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

## Struktur

```
CLAUDE.md            Projektkontext für Claude Code
layers/              Jev-Layer (jev_client, gatekeeper, config, …)
tests/               Tests mit deutschen Beispielnachrichten
relay/               Telegram-Webhook → Grok-Bot-Webhook (später)
grokbot/RUNBOOK.md   Nachrichten, die 1:1 an Grok Bot gehen
docs/                Notizen, Recherche
```
