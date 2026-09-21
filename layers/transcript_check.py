"""Transkript-Check: Ist das STT-Ergebnis einer Sprachnachricht brauchbar?

Läuft vor dem Türsteher. State = {transkript, dauer_sekunden}. Zwei noul-Fragen.

    from layers.transcript_check import evaluate
    evaluate("äh also ich wollte mal fragen wegen dem Termin", 6)
    -> {"usable": True, "p_understandable": .., "p_truncated": ..}
"""

from __future__ import annotations

from typing import Any

from . import config
from .jev_client import ask, noul

TRANSCRIPT_QUESTIONS: dict[str, dict[str, Any]] = {
    "understandable": {
        "type": "noul",
        "instructions": {
            "frage": "Lässt sich aus diesem Transkript ein verständliches Anliegen an ein Büro entnehmen?",
            "hinweis": "Füllwörter, Umgangssprache und kleine Erkennungsfehler sind normal. "
                       "Unbrauchbar ist es, wenn Wörter keinen Sinn ergeben, die Sprache falsch erkannt "
                       "wurde oder nur Geräusche/Bruchstücke drin sind.",
        },
    },
    "truncated": {
        "type": "noul",
        "instructions": "Bricht das Transkript mitten im Satz ab oder fehlt offensichtlich das Ende der Nachricht?",
    },
}


def decide(answers: dict[str, Any]) -> dict[str, Any]:
    p_u = noul(answers, "understandable")
    p_t = noul(answers, "truncated")
    usable = p_u >= config.TRANSCRIPT_MIN_UNDERSTANDABLE and p_t < config.TRANSCRIPT_MAX_TRUNCATED
    return {"usable": usable,
            "p_understandable": round(p_u, 2), "p_truncated": round(p_t, 2)}


def evaluate(transcript: str, duration_s: float | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {"transkript": transcript}
    if duration_s is not None:
        state["dauer_sekunden"] = duration_s
    res = ask(state, TRANSCRIPT_QUESTIONS)
    d = decide(res["answers"])
    d["latency_ms"] = res.get("latency_ms")
    d["cost_usd"] = res.get("usage", {}).get("cost")
    return d
