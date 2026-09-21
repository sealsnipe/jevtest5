"""Minimal client for TypeSafe Jev via OpenRouter's System One API.

No SDK dependency – only `requests`. The API key is read from the
OPENROUTER_API_KEY environment variable and never logged.

Usage:
    from layers.jev_client import ask
    res = ask("Hallo, ich hätte gern einen Termin.", {
        "spam": {"type": "noul", "instructions": "Ist das Spam?"},
    })
    res["answers"]["spam"]["noul"]  # -> 0.02
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

try:  # optional: read OPENROUTER_API_KEY from <repo>/.env if not in the environment
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

OPENROUTER_URL = "https://openrouter.ai/api/v1/systemone"
DEFAULT_MODEL = "typesafe/jev-1.13"  # pinned; "~typesafe/jev-latest" moves
TIMEOUT_S = 30


class JevError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise JevError(
            "OPENROUTER_API_KEY ist nicht gesetzt. "
            "PowerShell: $env:OPENROUTER_API_KEY='sk-or-...'  |  bash: export OPENROUTER_API_KEY=sk-or-..."
        )
    return key


def ask(
    state: str | dict | list,
    questions: dict[str, dict[str, Any]],
    model: str = DEFAULT_MODEL,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Send one state and a bundle of questions to Jev. Returns the raw response
    plus `latency_ms`. All questions are evaluated in parallel by the model, so
    bundle everything you might need into one call."""
    payload = {"model": model, "state": state, "questions": questions}
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        # Optional OpenRouter attribution headers
        "HTTP-Referer": "https://github.com/sealsnipe/projekt-sekretaerin",
        "X-Title": "Projekt Sekretaerin",
    }
    http = session or requests
    t0 = time.perf_counter()
    resp = http.post(OPENROUTER_URL, json=payload, headers=headers, timeout=TIMEOUT_S)
    latency_ms = round((time.perf_counter() - t0) * 1000)

    if resp.status_code != 200:
        raise JevError(f"HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    if "answers" not in data:
        raise JevError(f"Unerwartete Antwort: {str(data)[:500]}")
    data["latency_ms"] = latency_ms
    return data


# --- small helpers for reading answers ---------------------------------------

def noul_uncertain(answers: dict, qid: str, band: float) -> bool:
    """True if a yes/no answer sits too close to 0.5 to act on."""
    return abs(float(answers[qid]["noul"]) - 0.5) <= band


def score_tail_mass(answers: dict, qid: str, threshold_norm: float) -> float:
    """Probability mass on score levels whose normalized value is >= threshold_norm."""
    a = answers[qid]
    probs = a.get("probabilities", {})
    top = len(a.get("legend", {}) or probs) - 1
    if top <= 0:
        return 0.0
    return sum(float(p) for lvl, p in probs.items() if int(lvl) / top >= threshold_norm)


def noul(answers: dict, qid: str) -> float:
    return float(answers[qid]["noul"])


def choice(answers: dict, qid: str) -> tuple[str, float]:
    a = answers[qid]
    return a["choice"], float(a.get("confidence", 0.0))


def score(answers: dict, qid: str, normalize: bool = True) -> tuple[float, float]:
    """Returns (score, confidence). With normalize=True the score is scaled to 0..1
    by dividing through the top level index."""
    a = answers[qid]
    s = float(a["score"])
    if normalize:
        top = len(a.get("legend", {})) - 1
        if top > 0:
            s = s / top
    return s, float(a.get("confidence", 0.0))
