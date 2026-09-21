"""Layer 2 – Autonomie-Regler: darf ein Entwurf ohne den Chef raus?

State = {anfrage, entwurf}. Drei Fragen in einem Request, Entscheidung in Code:

    from layers.autonomy_gate import evaluate
    evaluate("Termin nächste Woche Dienstag?", "Gerne, Dienstag 10 Uhr vorgemerkt. Passt das?")
    -> {"decision": "send" | "review", "reasons": [...], ...}
"""

from __future__ import annotations

from typing import Any

from . import config
from .jev_client import ask, noul, noul_uncertain, score, score_tail_mass

AUTONOMY_QUESTIONS: dict[str, dict[str, Any]] = {
    "fit": {
        "type": "noul",
        "instructions": {
            "frage": "Beantwortet der Entwurf genau das Anliegen der Anfrage, ohne etwas zu erfinden "
                     "oder am Thema vorbeizugehen?",
            "hinweis": "Eine höfliche Rückfrage nach fehlenden Angaben passt, wenn die Anfrage "
                       "unvollständig ist. Konkretisierungen wie ein Datum für 'nächste Woche Dienstag' "
                       "oder eine Uhrzeit zur Bestätigung sind kein Erfinden.",
        },
    },
    "commitment": {
        "type": "noul",
        "instructions": {
            "frage": "Enthält der Entwurf eine verbindliche Zusage, einen Preis, eine Frist, "
                     "ein Zugeständnis, eine rechtliche Aussage oder eine Entschuldigung mit Haftung?",
            "hinweis": "Einen Termin 'vormerken' und um Bestätigung bitten ist keine verbindliche Zusage.",
        },
    },
    "risk": {
        "type": "score",
        "instructions": "Was passiert im schlimmsten Fall, wenn dieser Entwurf so an den Absender geht?",
        "criteria": [
            "Nichts; der Absender bekommt eine Rückfrage oder Bestätigung, die jederzeit korrigierbar ist",
            "Kleine Unannehmlichkeit; ein Termin muss verschoben oder eine Info nachgereicht werden",
            "Ärger oder Kosten; der Absender verlässt sich auf eine falsche Aussage, Preis oder Frist",
            "Schaden; rechtliche Folgen, Vertrauensverlust, Weitergabe von Daten Dritter oder Beleidigung",
        ],
    },
}


def decide(answers: dict[str, Any]) -> dict[str, Any]:
    p_fit = noul(answers, "fit")
    p_commit = noul(answers, "commitment")
    risk, risk_conf = score(answers, "risk", normalize=True)

    reasons = []
    if p_fit < config.AUTONOMY_MIN_FIT:
        reasons.append("passt_nicht_zur_anfrage")
    if p_commit >= config.AUTONOMY_COMMITMENT_THRESHOLD:
        reasons.append("enthaelt_zusage")
    if risk >= config.AUTONOMY_RISK_THRESHOLD:
        reasons.append("risiko")
    unsure: list[str] = []
    if not reasons:  # would send: is that decision solid?
        if noul_uncertain(answers, "fit", config.UNCERTAIN_NOUL_BAND):
            unsure.append("fit")
        if noul_uncertain(answers, "commitment", config.UNCERTAIN_NOUL_BAND):
            unsure.append("commitment")
        if score_tail_mass(answers, "risk", config.AUTONOMY_RISK_THRESHOLD) >= config.UNCERTAIN_SCORE_TAIL:
            unsure.append("risk")
        if unsure:
            reasons.append("unsicher:" + ",".join(unsure))

    return {
        "decision": "review" if reasons else "send",
        "reasons": reasons,
        "uncertain": unsure,
        "p_fit": round(p_fit, 2),
        "p_commitment": round(p_commit, 2),
        "risk": round(risk, 2),
        "risk_confidence": round(risk_conf, 2),
    }


def evaluate(request: str, draft: str) -> dict[str, Any]:
    res = ask({"anfrage": request, "entwurf": draft}, AUTONOMY_QUESTIONS)
    d = decide(res["answers"])
    d["latency_ms"] = res.get("latency_ms")
    d["cost_usd"] = res.get("usage", {}).get("cost")
    d["model"] = res.get("model")
    return d


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print('Aufruf: python -m layers.autonomy_gate "<anfrage>" "<entwurf>"')
        raise SystemExit(2)
    print(json.dumps(evaluate(sys.argv[1], sys.argv[2]), ensure_ascii=False, indent=2))
