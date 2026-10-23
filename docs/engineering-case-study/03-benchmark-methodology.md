# 03 — Benchmark Methodology

## 1. What can and cannot be benchmarked in this repository

| Category | Applicable? | Reason |
|---|---|---|
| Backend API latency / throughput | **Yes** | Real FastAPI app, real HTTP |
| Concurrency behaviour of the generation path | **Yes, with a labelled simulated provider** | The provider is `NotImplementedError`; its *latency* is replaced by `time.sleep`, everything around it is real |
| Upload handling, failure handling, timeouts, storage | **Yes** | Real code paths |
| Model latency, token usage, cost per generation, output quality | **No** | There is no model call in the repo. Any number here would be fabricated. |
| GPU utilisation / local inference | **No** | No local model; the design calls an external image API |
| Web frontend (Next.js) build time, page latency, bundle size | **No (in this audit)** | Next.js could not be installed: the sandbox's package-registry access was blocked. Not substituted with anything. |
| Container start-up / image size | **No (in this audit)** | No Docker daemon available |
| Backend cold start | **Yes** | Process start → first healthy response |

The rule applied throughout: a scenario either measures real MOSAIC code, or it is not reported. Where a test double is unavoidable (the provider), the double replaces only the part that does not exist, and every table that uses it says so.

## 2. System under test

- **Code**: `apps/backend` at `c76a78a` ("baseline") and the same tree with the changes in [05](05-engineering-improvements.md) ("after"). The baseline is exported with `git archive` so before/after runs use identical harness code and differ only in `--src`.
- **Isolation**: [`benchmarks/run_backend.py`](../../benchmarks/run_backend.py) copies `app/` and `data/` into a fresh temp dir per scenario, optionally flips `tryReady` **in the copy**, and starts uvicorn (1 worker, `log_level=warning`, access log off). The repo's `data/recipes.json` and `storage/` are never touched.
- **Test doubles** (all opt-in flags, all printed in the start-up line):
  - `--provider sleep:S` — `_call_provider` sleeps *S* seconds then returns a 1×1 PNG. Also sets `API_KEY="SIMULATED"` so the live branch runs; no key is sent anywhere.
  - `--provider hang` — sleeps 3600 s (never returns within the test).
  - `--fallback-bytes N` — writes a synthetic *N*-byte PNG plus a complete provenance sidecar labelled `provider: SYNTHETIC-BENCHMARK`.

## 3. Environment

| Item | Value |
|---|---|
| Host | Cloud sandbox VM, 2 vCPU Intel Xeon @ 2.10 GHz (x86_64), 7.8 GB RAM, Linux 6.18 |
| Python / ASGI | Python 3.13.16; FastAPI 0.160.0 (installed from source — PyPI blocked), Starlette 1.7.0, uvicorn 0.54.0 |
| Load generator | Node.js 22.22.0, built-in `fetch` (undici), [`benchmarks/loadgen.mjs`](../../benchmarks/loadgen.mjs) |
| Network | loopback (127.0.0.1) |
| Important caveat | Load generator and server share the same 2 vCPUs. Absolute throughput is a property of this box, not of MOSAIC; **compare before/after, not against other systems**. |

## 4. Scenarios

| ID | Question | Workload | Sample size | Warm-up | Repetitions |
|---|---|---|---|---|---|
| **S1** | Latency/throughput per endpoint | `GET /api/health`, `/api/recipes`, `/api/recipes/seed-01`, `/api/results/{id}`; `POST /api/generate` in three outcomes: 403 (not ready), `mock`, `cached` with a 1.5 MB asset. Upload: a 4032×3024 JPEG (1.64 MB, seeded) | 1000 req (GET), 200 req (POST) per run | 100 / 20 req | 3 trials × concurrency {1, 8, 32}; report median of trial p50/p95/p99/rps |
| **S2** | Does a slow generation starve other routes? | N concurrent generations against a 5 s simulated provider; once the worker threads exist (poll, ≤3 s), issue one `GET /api/health` and time it. Two uploads: 1×1 PNG (isolates the thread pool) and the 1.64 MB photo (adds multipart parsing) | N ∈ {0, 20, 39, 40, 41, 60} | — | 3 trials per N, fresh server each trial |
| **S3** | How much does the server ingest before rejecting an oversized upload? | `curl -H "Expect:"` (browsers do not send `Expect: 100-continue`) multipart upload of PNG-magic + zero padding, to a ready and a not-ready recipe | 1, 8, 9, 64, 256 MB | — | 3 per size × recipe; median; `size_upload` from curl = bytes actually sent |
| **S4** | What does a hung provider do to the caller and the server? | 5 parallel `curl -m 20` generations against `--provider hang` | 5 | — | 1 |
| **S5** | Disk written per generate | 100 generations in `mock` and in `cached` (1.5 MB asset) mode; size delta of `storage/results` | 100 | — | 1 |
| **S6** | Cold start | spawn → first 200 from `/api/health` (includes imports) | 10 | — | median/min/max |
| **S7** | Is re-reading `recipes.json` on every request worth caching? | `timeit` of `load_recipes()` in-process | 2000 calls | — | best of 5 |

Why these and not others:

- **S2 and S4 target the two risks that matter the moment a real provider is plugged in** (provider calls are seconds long and occasionally hang). They are the cheapest experiments that can falsify the design claim in `main.py` ("health stays responsive while a generation is in flight").
- **S3** tests a specific comment in `generate()` ("no reason to pull 8MB off the wire") against what Starlette actually does.
- **S1** is a sanity baseline: it shows whether any change regresses the common paths, and what the non-generation overhead is. It is *not* presented as a capacity claim.
- No "requests per second for the AI endpoint" is reported as a product metric, because without a provider it measures file I/O, not generation.

## 5. Metrics and their definitions

- **Latency** = client-side time from request start to full response body (`performance.now()` in Node, `time_total` in curl, `perf_counter` in Python).
- **p50/p95/p99** = nearest-rank percentiles over the measured (post-warm-up) requests of a trial; the table reports the **median across trials**.
- **Throughput (rps)** = measured requests ÷ wall time of the measured phase.
- **Closed-loop caveat**: each worker waits for its response before sending the next request, so when the server stalls the generator also stalls (coordinated omission). S1 tails are therefore optimistic. S2 avoids this by timing a single independent probe.

## 6. Reproduction

```sh
# backend venv as in the README, then:
python3 benchmarks/make_fixtures.py                           # seeded 4032x3024 JPEG
git archive c76a78a apps/backend | tar -x -C /tmp/baseline-src
PY=apps/backend/.venv/bin/python
$PY benchmarks/run_scenarios.py --label baseline --src /tmp/baseline-src/apps/backend
MOSAIC_PROVIDER_TIMEOUT_S=5 $PY benchmarks/run_scenarios.py --label after
MOSAIC_MAX_CONCURRENT_GENERATIONS=40 $PY benchmarks/run_scenarios.py --label after-limit40 --only S2
python3 benchmarks/report.py                                  # tables + charts
```

Needs: Python ≥ 3.10 with the backend requirements plus `psutil` and `matplotlib`; Node ≥ 22; `curl`. Full run ≈ 35 minutes on the box above (S2 dominates: 36 server start-ups × ≥5 s).

`MOSAIC_PROVIDER_TIMEOUT_S=5` only affects S4 (it shortens the new deadline so the scenario finishes in seconds; the production default is 60 s).
