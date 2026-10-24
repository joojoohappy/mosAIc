# 03 · Benchmark methodology

## 1. What is worth measuring for this architecture

MOSAIC is an I/O-bound web service in front of a paid external model, limited by design to 2 concurrent model calls and 50 paid calls a day. That shapes which metrics mean anything.

| Category                                                           | Applies?                              | Why                                                                                                                                                                                                     |
| ------------------------------------------------------------------ | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Read-endpoint latency p50/p95/p99, throughput                      | Yes                                   | Every page view hits `/api/recipes`, `/api/results/{id}`, `/static/results/{name}`. Cheap, repeatable, shows the cost of the framework and per-request file reads.                                      |
| End-to-end generation latency                                      | **Only MOSAIC's own share**           | Real Gemini latency (seconds) dominates and could not be measured: no API key, and paid calls were not approved. We measure everything around the model with a local fake, and report that as overhead. |
| Throughput of generation                                           | As a **designed cap**, not a capacity | With 2 slots and a model taking _T_ seconds, throughput is ≤ 2/_T_ per process by construction. The interesting measurement is what happens past the cap (shedding).                                    |
| Memory / CPU                                                       | Yes                                   | A generation holds the photo, its base64 copy and the JSON body in memory; this bounds concurrency on a 1–2 GB function.                                                                                |
| GPU, model inference, token throughput                             | **No**                                | MOSAIC hosts no model. Any such number would be fabricated.                                                                                                                                             |
| Token usage, cost per operation                                    | **Not measurable here**               | Needs real API responses. Cost is estimated in PR #2's docs from Google's price list (~$0.036/image); not re-derived.                                                                                   |
| Output validity / quality                                          | Partly                                | Validity of returned bytes (is it an image?) is tested. Visual quality needs real outputs and human review: not done.                                                                                   |
| Reliability (timeouts, failures, retries, duplicates, consistency) | **Yes, main focus**                   | This is where the design decisions live.                                                                                                                                                                |
| Deployment (build, start, restart, healthcheck)                    | Yes, backend container                | Vercel itself is not reachable from this sandbox.                                                                                                                                                       |
| Security (input validation, trust boundaries, injection exposure)  | Yes, targeted                         | Abuse controls are a large part of the code.                                                                                                                                                            |

## 2. Benchmarks

All scripts are in [`benchmarks/`](../../benchmarks/). Each writes JSON (summary + environment) and, where useful, raw per-request CSV to [`benchmarks/results/`](../../benchmarks/results/).

### B1 · Read-endpoint latency — [`bench_api.py`](../../benchmarks/bench_api.py), [`k6/read.js`](../../benchmarks/k6/read.js)

- **System under test:** one uvicorn worker (the shipped Docker command), from a throwaway copy of `apps/backend`, loopback HTTP/1.1, access log off.
- **Workload:** `GET` of 5 endpoints; one live result is created first (via the fake provider) so the result endpoints have data.
- **Load generator:** k6 v1.3.0, closed loop (`shared-iterations`), latency = k6 `http_req_duration`.
- **Levels:** concurrency 1, 8, 32. **Sample:** 200 warm-up requests discarded per cell, then 3 repetitions × 1,000 requests.
- **Also recorded:** server CPU (process tree, from `/proc`, 1.0 = one core) and peak RSS.
- **Why k6 and not Python:** a first attempt with an `httpx` async client measured _the client_. [`calibrate_client.py`](../../benchmarks/calibrate_client.py) puts both clients against the same server: `/api/health` at concurrency 32 → httpx p50 **102–110 ms** at 223 req/s with the server at 0.15 cores; k6 p50 **10.6–13.3 ms** at 2,200–2,800 req/s ([`client_calibration.json`](../../benchmarks/results/client_calibration.json)).
- B2 and B3 still use the httpx client: they run at concurrency 1 or measure counts and status codes, and baseline and after share the same client, so comparisons stay valid; absolute B2 latencies include a little client overhead.

### B2 · Generation pipeline overhead — [`bench_generate.py`](../../benchmarks/bench_generate.py), [`bench_stages.py`](../../benchmarks/bench_stages.py)

- **Model:** [`fake_gemini.py`](../../benchmarks/fake_gemini.py), a local server speaking the response shape `provider.py` parses. **All B2 numbers exclude real model time and say nothing about Gemini.**
- **overhead:** provider delay 0, concurrency 1, deterministic photo-like JPEGs of 0.3 MP (0.12 MB), 3 MP (1.2 MB), 12 MP (4.8 MB). 5 warm-up + 3 × 100 requests per size. Every request gets unique bytes appended after the JPEG end marker, so duplicate detection never short-circuits.
- **shedding:** provider delay 2 s, shipped `MOSAIC_MAX_CONCURRENT=2`, bursts of 10 and 20 simultaneous distinct uploads.
- **memory:** provider delay 1 s, 7.6 MB upload (12 MP, quality 97), concurrency 1 / 4 / 16, RSS sampled every 20 ms.
- **stages:** in-process timing (no HTTP) of `validate_upload`, SHA-256 fingerprint, `build_request` + `json.dumps`, `load_recipes`; median and p95 over 20–500 iterations.

### B3 · Reliability scenarios — [`bench_reliability.py`](../../benchmarks/bench_reliability.py)

Fresh backend per scenario, fake provider, `MOSAIC_PROVIDER_TIMEOUT=2` so timeouts are quick to observe.

| Scenario          | Provoked condition                                                                                                                         | Pass criterion                                                                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| provider_failures | ok, HTTP 500, hang 5 s, text-only 200, non-JSON 200, slow drip (1 byte / 100 ms), connection refused                                       | 200 with `mode=mock`/`cached` and the right `fallbackReason`; wall time ≤ timeout + small margin; never `live` without an image |
| duplicates        | same photo + recipe twice: simultaneous, 1 s apart (model takes 3 s), after completion                                                     | one provider call, same `resultId`                                                                                              |
| rate_limits       | 6 requests, each with a different forged `X-Forwarded-For`, default 3/min                                                                  | `[200,200,200,429,429,429]`                                                                                                     |
| daily_budget      | `MOSAIC_DAILY_GLOBAL=5`, 8 sequential requests                                                                                             | 5 × 200 then 503 `daily_budget_reached`; 5 provider calls                                                                       |
| budget_race       | `MOSAIC_DAILY_GLOBAL=50`, `MAX_CONCURRENT=2`, 300 requests from 16 threads, 1 and 4 uvicorn workers sharing one local store, 5 trials each | provider calls ≤ 50; no 500s                                                                                                    |
| body_limits       | 9 MB multipart with `Content-Length`, and chunked without                                                                                  | 413, server healthy                                                                                                             |
| corrupt_uploads   | 2048×1536 JPEG truncated to 99/90/50/10/1 %, 20 KB zeroed mid-file, valid control                                                          | damaged files rejected with 400 before the provider                                                                             |
| restart_recovery  | SIGTERM and SIGKILL, same storage                                                                                                          | result still readable; time to healthy                                                                                          |

### B4 · Container — [`bench_deploy.sh`](../../benchmarks/bench_deploy.sh)

Cold (`--no-cache`, base image already pulled) and warm build, image size, `docker run` → first 200 on `/api/health` (5 runs), `docker restart` → healthy (3 runs), whether a `HEALTHCHECK` is declared, container UID.

### Existing suite

`scripts/test-all.sh` (lint, ruff, unit, HTTP contract, Node client tests, production build, Playwright) is run before and after the changes.

## 3. Baseline vs. after

"Baseline" is PR #2's head `fbbc625`, checked out as a separate git worktree and passed in with `MOSAIC_BENCH_SRC=<worktree>/apps/backend`. "After" is this branch. Both runs use the same harness, machine, and session, back to back ([`run_all.sh`](../../benchmarks/run_all.sh)).

## 4. Environment

Recorded in every result file under `environment`. For this report: ephemeral cloud sandbox, 4 vCPU Intel Xeon @ 2.80 GHz, 15 GiB RAM, Linux 6.18, Python 3.13.16 (CI uses 3.12), Node 24.22.1, k6 1.3.0, Docker 29.9.1. Load generator and server share the machine; the machine is shared with other tenants. Treat absolute numbers as indicative of this box only; compare baseline and after only within the same run.

## 5. Known threats to validity

- **Same-host load generation.** k6 competes with uvicorn for 4 vCPUs. At concurrency 32 the server process never exceeded ~0.7 cores, so the client is not hiding a CPU-bound server, but tail latency includes scheduler noise.
- **Noisy neighbours.** Repetitions are reported separately so variance is visible.
- **Fake provider.** Measures MOSAIC's handling of provider behaviour, not the provider. Real Gemini may fail in ways not simulated (e.g. 429 quotas, partial streaming).
- **Local store only.** Vercel Blob adds a network round trip per read/write and was not available; result-read latency on Vercel will be higher than B1 shows.
- **Python 3.13 locally vs 3.12 in CI and Docker.**
- **Not measured:** real model latency, cost, output quality, Vercel cold starts, CDN behaviour, mobile networks.

## 6. Reproducing

```bash
python3 -m venv apps/backend/.venv
apps/backend/.venv/bin/pip install -r apps/backend/requirements-dev.txt
# k6: https://grafana.com/docs/k6/latest/set-up/install-k6/ (or set K6=/path/to/k6)

bash benchmarks/run_all.sh after          # this checkout, ~25 min
git worktree add /tmp/mosaic-baseline fbbc625
MOSAIC_BENCH_SRC=/tmp/mosaic-baseline/apps/backend bash benchmarks/run_all.sh baseline
bash benchmarks/bench_deploy.sh           # needs Docker
apps/backend/.venv/bin/pip install -r benchmarks/requirements.txt
apps/backend/.venv/bin/python benchmarks/charts.py
```
