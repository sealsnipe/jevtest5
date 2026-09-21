"""Local text-to-speech for the relay: text -> OGG/Opus voice note, on this PC.

Engine: Piper (piper-tts) with a German voice, default `de_DE-thorsten-medium`
(models/piper/, download see docs/stt_setup.md). No cloud, no key.

    from relay.tts import synthesize_ogg
    path = synthesize_ogg("Herr Müller, Dienstag um zehn Uhr ist vorgemerkt. Passt Ihnen das?")

Note: espeak-ng (used by Piper for phonemes) cannot handle non-ASCII paths on Windows;
the data dir is copied to %LOCALAPPDATA%/piper once if the venv path is non-ASCII.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VOICE = ROOT / "models" / "piper" / "de_DE-thorsten-medium.onnx"
_voice = None


def _espeak_data_dir() -> Path:
    from piper.phonemize_espeak import ESPEAK_DATA_DIR

    if str(ESPEAK_DATA_DIR).isascii():
        return ESPEAK_DATA_DIR
    base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "piper" / "espeak-ng-data"
    if not (base / "phontab").exists():
        shutil.copytree(ESPEAK_DATA_DIR, base, dirs_exist_ok=True)
    return base


def _load():
    global _voice
    if _voice is None:
        from piper import PiperVoice

        model = Path(os.environ.get("PIPER_VOICE", DEFAULT_VOICE))
        if not model.exists():
            raise RuntimeError(f"Piper-Stimme fehlt: {model} (siehe docs/stt_setup.md)")
        t0 = time.perf_counter()
        _voice = PiperVoice.load(str(model), espeak_data_dir=_espeak_data_dir())
        _voice._load_ms = round((time.perf_counter() - t0) * 1000)  # type: ignore[attr-defined]
    return _voice


def warmup() -> int:
    return _load()._load_ms  # type: ignore[attr-defined]


def synthesize_wav(text: str, wav_path: Path) -> None:
    with wave.open(str(wav_path), "wb") as w:
        _load().synthesize_wav(text, w)


def synthesize_ogg(text: str, out_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    """Returns (path to .ogg, timings). Caller deletes the file (or the temp dir)."""
    out_dir = out_dir or Path(tempfile.mkdtemp(prefix="tts_"))
    wav = out_dir / "reply.wav"
    ogg = out_dir / "reply.ogg"
    t0 = time.perf_counter()
    synthesize_wav(text, wav)
    t1 = time.perf_counter()
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libopus", "-b:a", "32k", "-ac", "1", "-application", "voip", str(ogg)],
        check=True,
    )
    t2 = time.perf_counter()
    with wave.open(str(wav)) as w:
        duration = round(w.getnframes() / w.getframerate(), 1)
    return ogg, {"tts_ms": round((t1 - t0) * 1000), "ffmpeg_ms": round((t2 - t1) * 1000), "duration_s": duration}


if __name__ == "__main__":
    import json
    import sys

    text = " ".join(sys.argv[1:]) or "Herr Müller, Dienstag um zehn Uhr ist vorgemerkt. Passt Ihnen das?"
    path, meta = synthesize_ogg(text, Path.cwd())
    print(json.dumps({"file": str(path), **meta}, ensure_ascii=False))
