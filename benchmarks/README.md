# Benchmarks

Reproducible measurements behind [`docs/engineering-case-study/`](../docs/engineering-case-study/README.md). Everything runs locally; nothing calls a paid API.

**The image model is simulated** by [`fake_gemini.py`](fake_gemini.py). Numbers involving `POST /api/generate` describe MOSAIC's own code around the model, never Gemini.

## Setup

```bash
python3 -m venv apps/backend/.venv
apps/backend/.venv/bin/pip install -r apps/backend/requirements-dev.txt
# k6 (read-latency load): https://grafana.com/docs/k6/latest/set-up/install-k6/
# or point K6=/path/to/k6 at a downloaded binary
apps/backend/.venv/bin/pip install -r benchmarks/requirements.txt   # charts only
```

Linux only (`/proc` is used for CPU and memory sampling).

## Run

```bash
bash benchmarks/run_all.sh after                       # this checkout, ~20 min
git worktree add /tmp/mosaic-baseline fbbc625          # PR #2 head
MOSAIC_BENCH_SRC=/tmp/mosaic-baseline/apps/backend bash benchmarks/run_all.sh baseline
apps/backend/.venv/bin/python benchmarks/calibrate_client.py
bash benchmarks/bench_deploy.sh                        # Docker; SKIP_BUILD=1 reuses an image
apps/backend/.venv/bin/python benchmarks/report_tables.py > benchmarks/results/tables.md
apps/backend/.venv/bin/python benchmarks/charts.py
```

Each benchmark starts its own uvicorn from a temporary copy of `apps/backend` (all seed recipes set `tryReady: true` in the copy only), so the repository's `storage/` and `recipes.json` are never touched.

## Files

| File                            | Purpose                                                                                                        |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `harness.py`                    | Backend launcher, fake-provider wrapper, `/proc` sampler, closed-loop client, percentiles, environment capture |
| `fake_gemini.py`                | Local model stand-in: `ok`, `error`, `hang`, `drip`, `text`, `badjson`; call counter                           |
| `bench_api.py` + `k6/read.js`   | B1 read-endpoint latency/throughput at concurrency 1/8/32                                                      |
| `bench_generate.py`             | B2 generate overhead by photo size, load shedding, memory                                                      |
| `bench_stages.py`               | B2b in-process stage timing                                                                                    |
| `bench_reliability.py`          | B3 failure, duplicate, rate-limit, budget, body-limit, corrupt-upload, restart scenarios                       |
| `compare_validation.py`         | Cost and detection of four upload-validation methods                                                           |
| `calibrate_client.py`           | Python httpx client vs k6 on the same server                                                                   |
| `bench_deploy.sh`               | B4 container build/start/restart                                                                               |
| `report_tables.py`, `charts.py` | Tables and charts from `results/`                                                                              |
| `results/`                      | Raw JSON/CSV/logs exactly as written by the scripts (excluded from Prettier)                                   |
