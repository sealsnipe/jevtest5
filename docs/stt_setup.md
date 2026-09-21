# Lokale Transkription: Parakeet v3 im Relay

Stand 2026-09-22. Sprachnachrichten werden auf dem Relay-PC transkribiert, bevor der Türsteher läuft.
Audio verlässt den Rechner nicht. Vorher hatte Grok Bot eigenmächtig Gemini über OpenRouter benutzt
(30 s pro Nachricht, Kunden-Audio bei Google, OpenRouter-Key zweckentfremdet).

## Was läuft

- Modell: `nvidia/parakeet-tdt-0.6b-v3` (25 Sprachen inkl. Deutsch), als ONNX über das Paket `onnx-asr`.
  Kein NeMo, kein PyTorch. Download ~2,5 GB beim ersten Start (Hugging-Face-Cache).
- Runtime: `onnxruntime-gpu` 1.30 mit CUDA 13 / cuDNN 9 aus pip-Wheels. Fallback CPU.
- Pipeline in `relay/stt.py`: Telegram `getFile` → ffmpeg (16 kHz mono wav) → `recognize()`.

## Messwerte (RTX 4070 Ti, 12 s Sprachnachricht)

| Schritt | GPU | CPU |
|---|---|---|
| Modell laden (einmal beim Relay-Start) | 3,6 s | 5,7 s |
| Download von Telegram | 0,2 s | 0,2 s |
| ffmpeg | 0,1 s | 0,1 s |
| Transkription | **0,44 s** | 4,8 s |

Zum Vergleich Grok Bot mit Gemini: 1:31 bis Download, 30 s Transkription, 2,5 min gesamt.

## Installation (Windows, venv)

```powershell
pip install "onnx-asr[gpu,hub]"
# CUDA-13-Laufzeit als Wheels (die "-cu13"-Metapakete haben KEINE Windows-Wheels, außer cudnn):
pip install nvidia-cublas nvidia-cuda-runtime nvidia-cudnn-cu13 nvidia-cufft nvidia-curand nvidia-cuda-nvrtc
```

`relay/stt.py` ruft `onnxruntime.preload_dlls()` auf, damit die DLLs aus den Wheels gefunden werden.
ffmpeg muss im PATH sein (hier: winget Gyan.FFmpeg).

Test ohne Relay:

```powershell
python -m relay.stt <telegram file_id>      # lädt über die Bot-API, braucht TELEGRAM_BOT_TOKEN in .env
python -m relay.stt aufnahme.oga            # lokale Datei
```

## Als Grok-Bot-Skill (falls STT auch dort laufen soll)

Grok-Bot-Computer hat keine GPU; CPU-Variante: `pip install "onnx-asr[cpu,hub]"`, Aufruf identisch.
Etwa 5 s pro 12 s Audio. Install als Skill ablegen, weil manuell installierte Pakete dort als
ersetzbar gelten (CLAUDE.md).

## Beobachtung

Transkript der ersten echten Nachricht: „Testnachricht Hallo hier wäre um. Könnten wir eben über meine
Rechnung reden vom zwölften Neunten zwanzig sechsundzwanzig?" – Eigenname „Werum" wurde zu „wäre um",
Rest korrekt. Zahlen kommen als Wörter, das passt zum Türsteher.

# Lokale Sprachsynthese: Piper im Relay

- Engine `piper-tts` 1.8 (GPL), Stimme `de_DE-thorsten-medium` aus `rhasspy/piper-voices` (63 MB) nach
  `models/piper/` (gitignored). Download:
  `https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx` (+ `.onnx.json`).
- Install: `pip install --no-deps piper-tts pathvalidate` (ohne `--no-deps` zieht es das CPU-`onnxruntime`
  und kollidiert mit `onnxruntime-gpu`).
- Windows-Falle: espeak-ng kann keine Nicht-ASCII-Pfade („Sekretärin"). `relay/tts.py` kopiert die
  espeak-Daten einmalig nach `%LOCALAPPDATA%\piper\espeak-ng-data`.
- Messwerte: laden 1,8 s (einmal), Synthese 0,24 s für 4,5 s Sprache, ffmpeg → Opus 0,12 s.
- Erste echte Sprachantwort 2026-09-22 01:10 über `POST /reply` an Telegram: ok, message_id 19.
