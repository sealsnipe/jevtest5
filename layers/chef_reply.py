"""Chef-Antwort einordnen: Was meint der Chef mit seiner Telegram-Nachricht?

State = {entwurf (worauf gewartet wird), antwort_chef}. Eine choice-Frage.

    from layers.chef_reply import evaluate
    evaluate("Entwurf: Termin Di 10 Uhr vorgemerkt…", "ja")
    -> {"kind": "freigabe" | "ablehnung" | "aenderung" | "anweisung" | "unklar", ...}
"""

from __future__ import annotations

from typing import Any

from . import config
from .jev_client import ask, choice, record

CHEF_REPLY_QUESTIONS: dict[str, dict[str, Any]] = {
    "kind": {
        "type": "choice",
        "instructions": "Die Sekretärin wartet auf eine Freigabe für den Entwurf. "
                        "Was bedeutet die Antwort des Chefs?",
        "criteria": {
            "freigabe": "Der Chef stimmt zu; der Entwurf soll so raus (z. B. 'ja', 'ok', 'passt', 'schick raus', Daumen hoch)",
            "ablehnung": "Der Chef will, dass nichts gesendet wird (z. B. 'nein', 'stopp', 'lass das', 'nicht senden')",
            "aenderung": "Der Chef will den Entwurf anders haben und sagt wie (anderer Text, andere Uhrzeit, anderer Ton)",
            "anweisung": "Der Chef gibt eine neue Aufgabe oder Regel, die nichts mit diesem Entwurf zu tun hat",
            "rueckfrage": "Der Chef stellt eine Frage zum Vorgang, bevor er entscheidet",
            "other": "Etwas anderes, z. B. Smalltalk oder eine Nachricht, die nicht an die Sekretärin gerichtet ist",
        },
    },
}


def decide(answers: dict[str, Any]) -> dict[str, Any]:
    kind, conf = choice(answers, "kind")
    if conf < config.CHEF_REPLY_MIN_CONFIDENCE:
        kind = "unklar"
    return {"kind": kind, "confidence": round(conf, 2),
            "probabilities": {k: round(v, 2) for k, v in answers["kind"].get("probabilities", {}).items()}}


def evaluate(pending_draft: str, chef_message: str) -> dict[str, Any]:
    state = {"wartender_entwurf": pending_draft, "antwort_chef": chef_message}
    res = ask(state, CHEF_REPLY_QUESTIONS)
    d = decide(res["answers"])
    d["latency_ms"] = res.get("latency_ms")
    d["cost_usd"] = res.get("usage", {}).get("cost")
    record("chef_reply", state, res, d)
    return d


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print('Aufruf: python -m layers.chef_reply "<wartender entwurf>" "<antwort chef>"')
        raise SystemExit(2)
    print(json.dumps(evaluate(sys.argv[1], sys.argv[2]), ensure_ascii=False, indent=2))
