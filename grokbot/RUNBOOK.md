# Runbook – Nachrichten an Grok Bot

Diese Nachrichten gehen 1:1 in Grok Bot (Desktop-App). Reihenfolge einhalten.
Vor jedem Schritt prüfen, ob der vorherige abgeschlossen ist. Nach jedem Schritt: Skill speichern lassen.

Voraussetzungen: Grok Bot installiert und eingeloggt (Cursor Pro+ / SuperGrok verknüpft),
OpenRouter-Key vorhanden, Telegram-Bot-Token von @BotFather.

---

## Schritt 1 – Bot "Empfang" anlegen

> Erstelle einen neuen Bot.
> Name: Empfang
> Job: Eingangskanal für Telegram-Nachrichten und Sprachnachrichten
> Beschreibung: Du nimmst Nachrichten aus Telegram entgegen, wandelst Sprachnachrichten in Text um
> und übergibst strukturierte Anfragen an den Bot "Sekretärin". Du antwortest Absendern nur mit
> kurzen Empfangsbestätigungen. Du sendest niemals Inhalte, Dokumente oder Kundendaten nach außen
> ohne Freigabe. Bei Passwörtern, 2FA oder CAPTCHAs fragst du mich.

## Schritt 2 – Telegram-Connector installieren

> Öffne den Marketplace und installiere das Telegram-Plugin (grokbot-telegram oder Composio).
> Konfiguriere es im Bot-API-Modus mit dem Token, das ich dir über die sichere Secret-Eingabe gebe.
> Bestätige mir, wenn du eine Testnachricht aus meinem Telegram-Chat lesen kannst.

(Token NICHT in den Chat tippen – die Secret-Eingabe des Plugins benutzen.)

## Schritt 3 – Jev-Türsteher als Skill installieren

> Im Ordner /workspace/sekretaerin liegen die Dateien layers/jev_client.py, layers/gatekeeper.py
> und layers/config.py. (Ich lade sie dir hoch / du klonst das Repo.)
> Lege den OpenRouter-Key als Umgebungsvariable OPENROUTER_API_KEY über die sichere Secret-Eingabe an.
> Führe `python tests/jev_smoke_test.py` aus und zeige mir die Tabelle.
> Speichere danach einen Skill "Jev Türsteher": Für jede eingehende Telegram-Nachricht rufst du
> `python -m layers.gatekeeper "<nachricht>"` auf und handelst nach dem Feld "action":
> - drop → Nachricht ignorieren, nur in /workspace/sekretaerin/log/dropped.jsonl schreiben
> - log → in /workspace/sekretaerin/log/inbox.jsonl schreiben, keine Übergabe
> - queue → Anfrage mit intent, urgency und Originaltext an den Bot "Sekretärin" übergeben
> - urgent → wie queue, zusätzlich mich sofort in diesem Chat anpingen

## Schritt 4 – Bot "Sekretärin" anlegen

> Erstelle einen neuen Bot.
> Name: Sekretärin
> Job: Anfragen bearbeiten – Termine, Rückrufe, Auskünfte, Dokumente, Tabelle pflegen
> Beschreibung: Du bekommst strukturierte Anfragen vom Bot "Empfang" (intent, urgency, Text).
> Du pflegst die Tabelle /workspace/sekretaerin/anfragen.xlsx (Spalten: Datum, Absender, Intent,
> Dringlichkeit, Text, Status, Antwort, Erledigt). Du erstellst Antwortentwürfe, Termine und Mails.
> Jede ausgehende Nachricht, jeder Termin und jede Mail braucht meine Freigabe, bis ich das
> ausdrücklich lockere. Fehlen Name, Termin oder Rückrufnummer, fragst du beim Absender nach.

## Schritt 5 – Connectors für die Sekretärin

> Installiere aus dem Marketplace: Google Calendar (oder Outlook), Gmail (oder Outlook Mail).
> Für Excel arbeitest du direkt mit openpyxl auf /workspace/sekretaerin/anfragen.xlsx.
> Zeige mir nach der Einrichtung einen Testeintrag in der Tabelle und einen Kalender-Entwurf.

## Schritt 6 – Routine + Webhook (Automatisierung)

> Lege für den Bot "Empfang" eine Routine mit Webhook-Trigger an und gib mir URL und Key.
> Die Routine soll: Payload lesen (Feld "text", optional "voice_file"), Sprachnachricht
> transkribieren, Skill "Jev Türsteher" ausführen und nach "action" handeln.
> Zusätzlich: Routine für "Sekretärin" täglich 08:00 Europe/Berlin: offene Einträge in
> anfragen.xlsx zusammenfassen und mir als Tagesreport in diesem Chat posten. Keine externen Aktionen.

(Webhook-URL + Key kommen dann in relay/.env – Relay verbindet Telegram-Webhook mit Grok-Bot-Webhook.)

## Schritt 7 – Test-Run

> Mach einen Test-Run der Empfangs-Routine mit diesem Payload: {"text": "Hallo, ich hätte gern
> einen Termin nächste Woche Dienstag um 10 Uhr. Gruß, Müller"} und zeig mir jeden Schritt.
> Erwartung: action=queue, intent=termin, Eintrag in anfragen.xlsx, Kalender-Entwurf zur Freigabe.

---

## Später (nach Layer 2)

- Skill "Autonomie-Regler": Entwurf + Originalanfrage an `layers/autonomy_gate.py`; bei
  hoher Konfidenz senden, sonst Freigabe.
- Parakeet v3 lokal installieren (Install-Skript als Skill), Grok-STT als Fallback.
- Mini App für Live-Voice (Grok Voice Agent API).
