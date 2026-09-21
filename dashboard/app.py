"""Jev-Entscheidungs-Dashboard (lokal, kein Tunnel).

Liest log/jev_decisions.jsonl (jede Layer-Auswertung: State, Jev-Antworten, Entscheidung)
und die Relay-Logs log/<action>.jsonl (was mit Telegram-Nachrichten passiert ist).

    uvicorn dashboard.app:app --port 8090
    -> http://127.0.0.1:8090
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = Path(os.environ.get("JEV_LOG_DIR", ROOT / "log"))
RELAY_ACTIONS = ("queue", "urgent", "chef", "block", "drop", "log", "rejected", "error")

app = FastAPI(title="Jev Dashboard")


def _read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/api/decisions")
def decisions(limit: int = 500) -> dict[str, Any]:
    jev = _read_jsonl(LOG_DIR / "jev_decisions.jsonl", limit)
    relay: list[dict[str, Any]] = []
    for action in RELAY_ACTIONS:
        for row in _read_jsonl(LOG_DIR / f"{action}.jsonl", limit):
            relay.append({"relay_action": action, **row})
    relay.sort(key=lambda r: r.get("ts", ""))
    return {"jev": jev, "relay": relay[-limit:]}
