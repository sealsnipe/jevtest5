"""Vorgangs-Zuordnung: Gehört eine neue Nachricht zu einem offenen Vorgang?

State = {nachricht, offene_vorgaenge: [{id, intent, text, status}]}. Eine choice-Frage,
Optionen werden dynamisch aus den offenen Vorgängen gebaut (+ "neu").

    from layers.matcher import evaluate
    evaluate("Hier die Nummer: 0176 1234567", [{"id": "A-12", "intent": "rueckruf", "text": "...", "status": "rueckfrage gesendet"}])
    -> {"case_id": "A-12" | None, "confidence": ..}
"""

from __future__ import annotations

from typing import Any

from . import config
from .jev_client import ask, choice


def build_questions(open_cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    criteria = {
        c["id"]: f"Fortsetzung von Vorgang {c['id']} ({c.get('intent', '?')}, Status: {c.get('status', '?')}): "
                 f"\"{str(c.get('text', ''))[:160]}\""
        for c in open_cases
    }
    criteria["neu"] = "Ein neues Anliegen, das zu keinem der offenen Vorgänge gehört"
    return {
        "case": {
            "type": "choice",
            "instructions": "Zu welchem offenen Vorgang desselben Absenders gehört diese neue Nachricht? "
                            "Eine Antwort auf eine Rückfrage, eine Nachlieferung (Nummer, Datum) oder "
                            "'wie besprochen' gehört zum bestehenden Vorgang.",
            "criteria": criteria,
        }
    }


def decide(answers: dict[str, Any]) -> dict[str, Any]:
    case_id, conf = choice(answers, "case")
    if case_id == "neu" or conf < config.MATCH_MIN_CONFIDENCE:
        case_id = None
    return {"case_id": case_id, "confidence": round(conf, 2),
            "probabilities": {k: round(v, 2) for k, v in answers["case"].get("probabilities", {}).items()}}


def evaluate(message: str, open_cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not open_cases:
        return {"case_id": None, "confidence": 1.0, "probabilities": {"neu": 1.0}, "latency_ms": 0, "cost_usd": 0.0}
    res = ask({"nachricht": message, "offene_vorgaenge": open_cases}, build_questions(open_cases))
    d = decide(res["answers"])
    d["latency_ms"] = res.get("latency_ms")
    d["cost_usd"] = res.get("usage", {}).get("cost")
    return d
