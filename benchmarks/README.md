# benchmarks/

Reproducible backend benchmarks for the engineering case study
([methodology](../docs/engineering-case-study/03-benchmark-methodology.md),
[results](../docs/engineering-case-study/04-benchmark-results.md)).

**No AI model is measured here — the repository has none yet.** Where a scenario needs
a provider, `run_backend.py --provider sleep:S|hang` replaces only the missing
`_call_provider`; everything else is the real FastAPI app.

| File | Purpose |
|---|---|
| `run_backend.py` | Starts the real app from an isolated temp copy; optional labelled test doubles |
| `loadgen.mjs` | Zero-dependency closed-loop HTTP load generator (Node ≥ 22) |
| `run_scenarios.py` | Scenarios S1–S7; writes `raw/<label>/` and `results/<label>.json` |
| `report.py` | `results/summary.md` + `charts/*.png` (all doc figures come from here) |
| `make_fixtures.py` | Seeded 4032×3024 JPEG upload fixture |
| `fixtures/` | Upload fixtures |
| `raw/` | Per-request samples (`[latency_ms, status]`) for every S1/S5 run |
| `results/` | `baseline.json`, `after.json`, `after-limit40.json`, `summary.md` |
| `charts/` | PNG charts used in the docs |

```sh
pip install -r benchmarks/requirements.txt          # into the backend venv
python3 benchmarks/make_fixtures.py
git archive c76a78a apps/backend | tar -x -C /tmp/baseline-src
PY=apps/backend/.venv/bin/python
$PY benchmarks/run_scenarios.py --label baseline --src /tmp/baseline-src/apps/backend
MOSAIC_PROVIDER_TIMEOUT_S=5 $PY benchmarks/run_scenarios.py --label after
MOSAIC_MAX_CONCURRENT_GENERATIONS=40 $PY benchmarks/run_scenarios.py --label after-limit40 --only S2
python3 benchmarks/report.py
```
