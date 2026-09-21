"""Local speech-to-text for the relay: Telegram voice note -> text, on this PC.

Model: NVIDIA Parakeet TDT 0.6B v3 via onnx-asr (ONNX Runtime, CUDA if available,
CPU otherwise). 25 European languages incl. German, no cloud, no API key.

    from relay.stt import transcribe_telegram_voice
    text, meta = transcribe_telegram_voice(file_id)      # needs TELEGRAM_BOT_TOKEN

Audio never leaves the machine: Telegram getFile -> ffmpeg -> 16 kHz mono wav -> model.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"
_model = None


def _load():
    global _model
    if _model is None:
        import onnx_asr  # lazy: heavy import, only when a voice note arrives

        t0 = time.perf_counter()
        _model = onnx_asr.load_model(MODEL_NAME, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _model._load_ms = round((time.perf_counter() - t0) * 1000)  # type: ignore[attr-defined]
    return _model


def warmup() -> int:
    """Load the model at relay start so the first voice note is not slow."""
    return _load()._load_ms  # type: ignore[attr-defined]


def download_telegram_file(file_id: str, token: str, dest: Path) -> int:
    r = requests.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=15)
    r.raise_for_status()
    info = r.json()
    if not info.get("ok"):
        raise RuntimeError(f"getFile: {info}")
    path = info["result"]["file_path"]
    with requests.get(f"https://api.telegram.org/file/bot{token}/{path}", stream=True, timeout=60) as f:
        f.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in f.iter_content(65536):
                fh.write(chunk)
    return dest.stat().st_size


def to_wav16k(src: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )


def transcribe_wav(wav: Path) -> str:
    return (_load().recognize(str(wav)) or "").strip()


def transcribe_telegram_voice(file_id: str) -> tuple[str, dict[str, Any]]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nicht gesetzt")
    meta: dict[str, Any] = {"model": MODEL_NAME}
    with tempfile.TemporaryDirectory(prefix="voice_") as tmp:
        oga = Path(tmp) / "in.oga"
        wav = Path(tmp) / "in.wav"
        t0 = time.perf_counter()
        meta["bytes"] = download_telegram_file(file_id, token, oga)
        t1 = time.perf_counter()
        to_wav16k(oga, wav)
        t2 = time.perf_counter()
        text = transcribe_wav(wav)
        t3 = time.perf_counter()
    meta.update(download_ms=round((t1 - t0) * 1000), ffmpeg_ms=round((t2 - t1) * 1000), stt_ms=round((t3 - t2) * 1000))
    return text, meta


if __name__ == "__main__":
    import json
    import sys

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if len(sys.argv) < 2:
        print("Aufruf: python -m relay.stt <telegram file_id | pfad.wav/.oga>")
        raise SystemExit(2)
    arg = sys.argv[1]
    if Path(arg).exists():
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "in.wav"
            to_wav16k(Path(arg), wav)
            t0 = time.perf_counter()
            print(json.dumps({"text": transcribe_wav(wav), "stt_ms": round((time.perf_counter() - t0) * 1000)}, ensure_ascii=False))
    else:
        text, meta = transcribe_telegram_voice(arg)
        print(json.dumps({"text": text, **meta}, ensure_ascii=False, indent=2))
