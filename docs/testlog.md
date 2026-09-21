# Testlog – Jev Smoke Test

Aufruf: `python tests/jev_smoke_test.py` (braucht `OPENROUTER_API_KEY`). Modell: `typesafe/jev-1.13` gepinnt.

| Datum | Modellversion | Samples | action | intent | Ø Latenz | Kosten | Bemerkung |
|---|---|---|---|---|---|---|---|
| 2026-09-21 | typesafe/jev-1.13-20260917 | 12 | 12/12 | 10/12 | 388 ms (min 292) | $0.00039 | Test 0, 4 Fragen. Abweichungen: #5 (termin statt bestaetigung, Erwartung geändert), #12 (Injection nur halb erkannt, spam 0.42) |
| 2026-09-21 | _ausstehend_ | 14 | – | – | – | – | 5 Fragen (injection), #12 → block, 2 neue Samples (#13 block, #14 queue). Lauf steht aus: Key war in der Claude-Code-Session nicht gesetzt. |

Nach dem nächsten Lauf hier eintragen. Bei action < 13/14 zuerst `INJECTION_BLOCK_THRESHOLD`
in `layers/config.py` prüfen (Sample #14 „Steuerberater" darf **nicht** blocken).
