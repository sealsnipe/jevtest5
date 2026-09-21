"""Voice-Check: Taugt ein Antworttext als gesprochene Sprachnachricht?

Regeln aus docs/voice_rules.md. Zählbares wird in Code geprüft (Wörter, Sätze, Fragen,
Ziffern, Listen, Floskeln). Jev bekommt nur, was Code nicht kann: klingt es gesprochen
natürlich, ist es ein Thema, ist der Vorspann/Abspann weg.

    from layers.voice_check import evaluate
    evaluate("Herr Müller, Dienstag um zehn Uhr ist vorgemerkt. Passt Ihnen das?")
    -> {"ok": True, "hints": [], ...}
"""

from __future__ import annotations

import re
from typing import Any

from . import config
from .jev_client import ask, noul, record

VOICE_QUESTIONS: dict[str, dict[str, Any]] = {
    "natural": {
        "type": "noul",
        "instructions": {
            "frage": "Klingt dieser Text laut vorgelesen wie ein kurzer, natürlicher Satz einer "
                     "Sekretärin am Telefon, nicht wie eine geschriebene E-Mail?",
            "hinweis": "Schriftsprache-Signale: Grußformeln, Abkürzungen, Aufzählungen, lange "
                       "Schachtelsätze, Ziffern und Datumsformate wie 29.09.",
        },
    },
    "one_topic": {
        "type": "noul",
        "instructions": {
            "frage": "Behandelt der Text genau ein Anliegen, nicht mehrere?",
            "hinweis": "Eine Aussage mit der direkt dazugehörigen Rückfrage ('Dienstag ist vorgemerkt. "
                       "Passt das?') ist ein Anliegen. Zwei Anliegen sind z. B. Terminbestätigung plus "
                       "Frage nach der Telefonnummer, oder Termin plus Rechnung.",
        },
    },
    "filler": {
        "type": "noul",
        "instructions": {
            "frage": "Enthält der Text einen Vorspann oder Abspann ohne Inhalt, etwa Dank für die "
                     "Nachricht, 'gerne helfe ich', Grußformel oder Signatur?",
            "hinweis": "Eine Anrede mit Namen am Anfang ist kein Vorspann.",
        },
    },
}

_OPENERS = re.compile(
    r"^(vielen dank|danke für ihre nachricht|gerne helfe|gern helfe|schön, dass|guten tag,?\s*(vielen|danke))", re.I)
_CLOSERS = re.compile(
    r"(viele grüße|freundliche grüße|mit freundlichen|liebe grüße|ihre sekretärin|ihr team|melden sie sich gern|"
    r"bei fragen stehe|stehe ich .* zur verfügung)\W*$", re.I)
_ABBREV = re.compile(r"\b(z\.\s?B\.|bzw\.|ca\.|evtl\.|ggf\.|usw\.|Nr\.|Tel\.|Str\.)", re.I)


def check_static(text: str) -> list[str]:
    """Rule violations that need no model. Returns hint strings (empty = fine)."""
    t = text.strip()
    hints: list[str] = []
    words = len(re.findall(r"\b[\wäöüß'-]+\b", t, re.I))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
    if words > config.VOICE_MAX_WORDS:
        hints.append(f"zu lang: {words} Wörter, maximal {config.VOICE_MAX_WORDS}")
    if len(sentences) > config.VOICE_MAX_SENTENCES:
        hints.append(f"zu viele Sätze: {len(sentences)}, maximal {config.VOICE_MAX_SENTENCES}")
    if t.count("?") > 1:
        hints.append("mehr als eine Frage")
    if t.count("!") > 1:
        hints.append("mehr als ein Ausrufezeichen")
    if re.search(r"\d", t):
        hints.append("Ziffern enthalten: Zahlen, Uhrzeiten, Daten ausschreiben")
    if re.search(r"^\s*([-*•]|\d+[.)])\s", t, re.M) or "\n" in t:
        hints.append("Aufzählung oder Zeilenumbruch: als Fließtext formulieren")
    if re.search(r"[()\[\]*_#]", t):
        hints.append("Klammern oder Markdown-Zeichen")
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", t):
        hints.append("Emoji")
    if _ABBREV.search(t):
        hints.append("Abkürzung ausschreiben")
    if _OPENERS.search(t):
        hints.append("Vorspann streichen, mit der Sache anfangen")
    if _CLOSERS.search(t):
        hints.append("Abspann streichen, mit dem letzten Inhaltswort oder der Frage enden")
    if re.search(r"\b(oder|beziehungsweise)\b.*\b(oder|beziehungsweise)\b", t, re.I):
        hints.append("mehr als zwei Optionen genannt")
    return hints


def decide(answers: dict[str, Any], static_hints: list[str]) -> dict[str, Any]:
    p_nat = noul(answers, "natural")
    p_one = noul(answers, "one_topic")
    p_fill = noul(answers, "filler")
    hints = list(static_hints)
    if p_nat < config.VOICE_MIN_NATURAL:
        hints.append("klingt geschrieben, nicht gesprochen")
    if p_one < config.VOICE_MIN_ONE_TOPIC:
        hints.append("mehr als ein Thema: in zwei Nachrichten teilen")
    if p_fill >= config.VOICE_MAX_FILLER:
        hints.append("Vorspann oder Abspann ohne Inhalt")
    return {"ok": not hints, "hints": hints,
            "p_natural": round(p_nat, 2), "p_one_topic": round(p_one, 2), "p_filler": round(p_fill, 2)}


def evaluate(text: str) -> dict[str, Any]:
    static_hints = check_static(text)
    state = {"antworttext": text}
    res = ask(state, VOICE_QUESTIONS)
    d = decide(res["answers"], static_hints)
    d["latency_ms"] = res.get("latency_ms")
    d["cost_usd"] = res.get("usage", {}).get("cost")
    record("voice_check", state, res, d)
    return d


if __name__ == "__main__":
    import json
    import sys

    text = " ".join(sys.argv[1:])
    if not text:
        print('Aufruf: python -m layers.voice_check "<antworttext>"')
        raise SystemExit(2)
    print(json.dumps(evaluate(text), ensure_ascii=False, indent=2))
