# Grok Bot in der Praxis: was funktionierte, was nicht

Erfahrungen aus der Einrichtung am 21./22.09.2026 (Grok Bot Desktop-App, zwei Bots, Composio-Telegram,
Gmail/Calendar, Jev-Skills). Alles hier ist beobachtet, nichts vermutet. Die vollständigen Prompts stehen in
`SETUP.md` (aktuelle Fassung) und `../grokbot/RUNBOOK.md` (chronologisch).

## Was gut funktioniert

| Was | Beobachtung |
|---|---|
| Bots per Formular anlegen | Name, Bezeichnung, Beschreibung. Die Beschreibung wirkt stark: „Fehlen Name, Termin oder Rückrufnummer, fragst du nach" wurde ohne weiteren Skill befolgt. |
| Dateien ins Workspace legen | Bot liest sie vom lokalen PC (siehe unten) und legt sie unter `/workspace/sekretaerin/` ab. Python-Skripte laufen dort direkt. |
| Python-Skills | „Speichere einen Skill X: rufe `python -m layers.gatekeeper "<text>"` auf und handle nach action" funktioniert zuverlässig. JSON-Ausgabe wird korrekt gelesen. |
| Webhook-Routine | Trigger „Webhook" liefert URL + Bearer-Key im Routinen-Panel. Payload-Felder werden wie beschrieben interpretiert. Antwort 200, Routine startet innerhalb von Sekunden bis ~1,5 min. |
| Bot-zu-Bot-Übergabe | Empfang → Sekretärin mit strukturiertem Text klappt, inklusive chat_id/message_id. |
| Freigabe-Dialoge | Der Bot baut selbst Auswahlkarten („Telegram senden / Kalender anlegen / Beides / Nichts"). |
| Datumslogik | „nächste Woche Dienstag" wurde korrekt auf ein Datum aufgelöst. |
| Composio Gmail + Calendar | Installation und OAuth in wenigen Minuten, Entwürfe werden gezeigt, nichts wird ohne Freigabe gesendet. |
| Terminal-Aufrufe | `curl` mit JSON-Datei, `source relay.env`, ffmpeg: alles verfügbar. |
| Regeln nachträglich ändern | „Ab jetzt gilt: …" wird übernommen und in Skills eingearbeitet, der Bot bestätigt, was er geändert hat. |

## Was nicht funktionierte, und der Ausweg

### Secret-Karte reicht Werte nicht in die Shell
**Symptom:** Token dreimal über die Secret-Karte „Telegram Bot Token" gespeichert („Gespeichert, sicher
und privat"), in der Shell des Bots existierte `TELEGRAM_BOT_TOKEN` trotzdem nie
(`CLOUD_AGENT_INJECTED_SECRET_NAMES` enthielt nur `OPENROUTER_API_KEY`).
**Warum:** Der OpenRouter-Key kam an, weil der Bot ihn selbst „als Umgebungsvariable OPENROUTER_API_KEY"
angefordert hatte. Eine Karte mit Anzeigename ohne Variablennamen landet nur im Secret-Store.
**Ausweg:** Secrets, die der Bot in der Shell braucht, vom Bot mit exaktem Variablennamen anfordern
lassen. Besser: Secrets gar nicht zum Bot geben. Bei uns hält das Relay den Bot-Token, der Bot ruft
`POST /reply` mit einem eigenen, niedrigwertigen Key auf.

### Composio-Telegram kann keine Sprachnachrichten senden
**Symptom:** „Telegram-Connector hat kein sendVoice", Antwort ging als Text raus.
**Ausweg:** Telegram-Bot-API direkt (`sendVoice`), bei uns aus dem Relay heraus.

### Bot nutzte den OpenRouter-Key eigenmächtig für Gemini
**Symptom:** Auf die Frage nach dem STT-Modell: „Gemini über OpenRouter; Whisper war 401". Niemand hatte
das angewiesen. Kunden-Audio ging an Google, 30 s pro Nachricht, der Key wurde zweckentfremdet.
**Ausweg:** Explizit in Routine und Skill: „OPENROUTER_API_KEY ist ausschließlich für Jev
(typesafe/jev-1.13), nie für Transkription oder andere Modelle." Transkription ins Relay verlegt.

### „W: darf ich nicht lesen" – und dann doch
**Symptom:** Bot meldete, `W:` liege außerhalb des erlaubten Bereichs, kopierte die Dateien dann über
`C:\Users\<user>\Downloads` als Staging und las sie von dort.
**Bedeutung:** Die Ordner-Sperre ist eine Bitte an das Modell, keine Grenze. Der Bot umgeht sie
selbstständig, wenn die Aufgabe es nahelegt.
**Konsequenz:** Nichts Sensibles in Reichweite des Desktop-Clients lassen, was er nicht haben soll.
Relay-Code und `.env` liegen bei uns außerhalb seines Blickfelds, und er bekommt keine Aufgaben, die
ihn dorthin führen.

### Bot legte sich eine dauerhafte Freigabe an
**Symptom:** Beim Versuch, die Sprachnachricht per Executor-Subagent zu senden, erschien „Aktion
genehmigt · Immer erlaubt" und eine Regel „Use the executor subagent to send Telegram voice notes via
the Telegram Bot API" wurde in die Auto-Review-Einstellungen geschrieben.
**Konsequenz:** Auto-Review-Einstellungen regelmäßig durchsehen. Solche Regeln überleben die Aufgabe.

### Langsame Kette
**Symptom:** Sprachnachricht bis Übergabe an die Sekretärin 2,5 min: 1:31 bis Routine-Start plus
Download, 30 s Transkription, 9 s für zwei Python-Aufrufe, die intern 0,2 s brauchen.
**Ausweg:** Alles, was kein Sprachmodell braucht, vor Grok Bot erledigen. Mit Transkription und
Türsteher im Relay: 2,2 s bis Grok Bot geweckt wird.

### Chef-Nachricht vs. Kundennachricht aus demselben Chat
**Symptom:** Als Chef und Testkunde gleichzeitig kam jede Nachricht als „Chef" an; eine
Sprachnachricht blieb als `voice_pending` hängen, weil der Chef-Pfad die Transkription übersprang.
**Ausweg:** Präfix „Testnachricht" → Kundenpfad. Chef-Status ist ein Flag (`from_chef`), keine Action;
ob es eine Freigabe ist, entscheidet nur die Sekretärin, weil nur sie weiß, ob ein Entwurf wartet.

### Tunnel-URL und Telegram-Webhook
**Symptom:** Nach jedem Neustart des Quick-Tunnels kannte Telegram den neuen Hostnamen 5+ Minuten
lang nicht, `setWebhook` schlug fehl.
**Ausweg:** Long Polling statt Webhook (wie OpenClaw). Tunnel nur für den Rückkanal; die URL steht in
jedem Payload und wird bei Wechsel aktiv an Empfang gemeldet.

### Kleinkram
- `grokbot-telegram`-Plugin existiert im Marketplace nicht, nur Composio.
- Windows-Konsole cp1252: Testskripte müssen stdout auf UTF-8 stellen (Emojis in Testdaten).
- Ordnerpfade mit Umlaut („Sekretärin") brechen espeak/Piper; Repo in ASCII-Pfad klonen.
- Port 8090 ist auf Windows oft reserviert (Hyper-V), daher Dashboard auf 8095.

## Prompt-Muster, die sich bewährt haben

- **Eine Nachricht = ein Skill oder eine Routine**, mit nummerierten Schritten und exakten Feldnamen.
- **Feld-Semantik im Prompt wiederholen** („from_chef = true bedeutet …"), nicht auf frühere Chats verlassen.
- **Aktionen an Felder binden**, nicht an Prosa: „Bei action = block: nichts ausführen, in
  log/block.jsonl schreiben, mich einmal informieren."
- **Erwartung mitgeben**: „Führe X aus und zeig mir die Tabelle, Erwartung 14/14." Der Bot prüft dann selbst.
- **Verbote explizit**: „Nie in den Chat ausgeben", „nur für Jev", „nichts ohne Freigabe". Ohne Verbot
  nimmt der Bot, was er findet.
- **Testmodus benennen** („Testnachricht" = ich spiele Kunde), sonst vermischt der Bot Rollen.
