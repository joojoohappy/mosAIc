# 05 — Engineering Improvements

Selection rule: fix what (a) was demonstrated by a measurement or a failing run, (b) will matter as soon as a real provider is attached, (c) can be done without changing the public API contract or adding infrastructure. Each change below follows: problem → baseline → alternatives → change → regression → re-measurement.

Full diff: `git diff c76a78a -- apps/backend .github`.

| # | Change | Files | Lines (approx.) |
|---|---|---|---|
| I1 | Dedicated generation limiter; `async` health | `main.py`, `generation.py` | ~15 |
| I2 | Bounded provider response time (fallback at a deadline) | `generation.py`; +3 tests | ~25 + 42 test |
| I3 | Upload size limit before multipart parsing | `main.py`; +3 smoke checks | ~60 + 8 test |
| I4 | Bounded start-up wait in the smoke test | `test_api.sh` | ~9 |
| I5 | CI workflow | `.github/workflows/ci.yml` | 45 (**unexecuted**) |
| I6 | Document new env knobs | `.env.example` | 6 |

---

## I1 — Isolate generation from the shared thread pool (ADR-7)

1. **Problem**: every sync `def` route shares AnyIO's 40-thread limiter. Generation holds a thread for the whole provider call.
2. **Baseline**: S2 — `/api/health` 2.8 ms at 39 in flight, **4,818.9 ms at 40**, 4,887.7 ms at 60.
3. **Alternatives**: raise the global limit (moves the cliff, more memory); full async provider client (no provider chosen); job queue (contract change). See ADR-7.
4. **Change**:
   - `generate` is `async def`; reads the upload with `await image.read(MAX_BYTES + 1)`; runs `run_generation` with `anyio.to_thread.run_sync(..., limiter=_generation_slots)`.
   - `_generation_slots = anyio.CapacityLimiter(MAX_CONCURRENT_GENERATIONS)`, env `MOSAIC_MAX_CONCURRENT_GENERATIONS`, default 8.
   - `health` is `async def` with no I/O.
   - Read routes stay `def` (their file reads are ~30 µs; nothing to gain from rewriting them).
5. **Regression**: 39/39 unit, 20/20 smoke, 9/9 client, 5/5 wire.
6. **Re-measurement** (S2, median of 3): health at 40 / 60 in flight = **2.0 / 2.0 ms** (limit 8) and **2.1 / 2.1 ms** (limit 40).
7. **Regressions / costs**: with limit 8, completing 60 simulated 5 s generations takes 40.1 s instead of 10.1 s — by design; set the limit from the provider's rate limit. `POST generate → mock` p50 +1.0 ms at concurrency 1 (S1).

An intermediate version used a separate `MOSAIC_PROVIDER_WORKERS` knob for the provider pool. Running S2 with limit 40 showed generation time stuck at the 8-slot rate: the provider pool (8) silently overrode the limiter (40). The knob was removed; the pool is now derived as 2 × the limit, and S2 was re-run on the final code.

## I2 — Bounded response time for provider calls (ADR-8)

Wording note: this bounds how long the *caller* waits. It does not stop the provider call — a started Python thread keeps running and may still consume resources or provider credit.

1. **Problem**: `_call_provider`'s docstring requires "a hard deadline"; nothing enforced it.
2. **Baseline**: S4 — 5 requests against a hung provider: no response until the client's 20 s timeout; nothing returned.
3. **Alternatives**: rely on the future SDK's timeout only; `signal.alarm`; asyncio timeout. See ADR-8.
4. **Change**: `_call_provider_with_deadline()` submits to a `ThreadPoolExecutor(max_workers=2 × limit)` and waits `MOSAIC_PROVIDER_TIMEOUT_S` (default 60 s, matching the documented contract). On timeout: `future.cancel()` (prevents a queued call from ever starting) and raise `TimeoutError("provider exceeded the …s deadline")`, which `run_generation` already turns into a fallback. Catches `concurrent.futures.TimeoutError` explicitly because it is not the builtin `TimeoutError` before Python 3.11 (README supports ≥3.10).
5. **New tests** (`ProviderDeadline`): overrun → `cached` within the deadline with the reason recorded; an abandoned call that finishes later leaves **only** the result JSON on disk (invariant 1 under a deadline); a fast provider is unaffected.
6. **Re-measurement** (S4 with a 5 s deadline): 5 × `200` at **5.06–5.08 s**, `mode: mock`, reason recorded; health 2.0 ms afterwards.
7. **Remaining limitation**: abandoned threads keep running (5 extra threads observed in S4) and may still be billed by a real provider.

## I3 — Enforce the upload limit before parsing (ADR-9)

1. **Problem**: FastAPI/Starlette parse and spool the entire multipart body before the route runs; the route's size check comes too late.
2. **Baseline**: S3 — 256 MB → client sent all 268,435,779 bytes (server parsed all of it), 674–737 ms, then 400/403. F4: the 403 path costs 7.4 ms vs 9.7 ms for a full mock generation.
3. **Alternatives**: reverse-proxy limit (no proxy exists; recommended in addition); in-route `Content-Length` check (too late).
4. **Change**: pure-ASGI `UploadSizeLimit` on `POST /api/generate`, limit `8 MiB + 64 KiB`:
   - declared `Content-Length` over the limit → `400 {"error":"too_large"}` without reading the body;
   - chunked bodies: count bytes in `receive()`; on crossing the limit send the same 400 and hand the app a synthetic `http.disconnect`, then drop anything the app tries to send.
   The first version raised an exception from `receive()`; FastAPI caught it during form parsing and answered `{"detail":"There was an error parsing the body"}` — correct status, wrong code, which the frontend would show as "request failed". Found by adding smoke checks that assert the **body**.
5. **Regression**: +3 smoke checks (chunked oversize status; body code with and without chunking) → 20/20. The wire test's 8 MiB + 1 case still returns `too_large` from the route (it is under the framing allowance), unchanged.
6. **Re-measurement** (S3): 256 MB → **client had sent ≤ 1.25 MB when rejected, ~1 ms**; 9 MB → ≤ 1.77 MB, ~1 ms (curl `size_upload`: bytes sent by the client, not bytes read by the server); 1 MB and 8 MB unchanged.
7. **Behaviour changes**: oversized + not-ready now `too_large` (was `recipe_not_ready`); Node undici and Python urllib see a connection reset instead of the 400 (Chromium and curl read it).

## I4 — Bounded wait in `test_api.sh`

- **Problem / baseline**: the script hung indefinitely in this audit when `uvicorn` failed to start (no entry point in the venv) — F7.
- **Change**: 15 s bounded loop that also detects the server process exiting; mirrors `scripts/dev.sh`.
- **Verification**: script passes (20/20). The hang case was reproduced before the fix, not re-reproduced after (the failure condition was removed from the environment).

## I5 — CI workflow (unexecuted)

`.github/workflows/ci.yml` runs: backend unit tests, the HTTP smoke test, `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm test` (client + wire), `pnpm build`. **It has never run.** First run may need adjustments (e.g. pnpm 11 via `packageManager`, Node 24).

## Considered and not implemented

See ADR-10: recipe caching (31 µs — not worth it), referencing instead of copying fallback images (breaks immutability), dependency pinning (would fabricate a tested configuration), job queue (contract change), client-side image downscaling (frontend not buildable here).

## Net effect

| Metric | Baseline | After |
|---|---|---|
| Health latency, 40 slow generations in flight | 4,818.9 ms | 2.0 ms |
| Hung provider: time to a response | none within 20 s | 5.06–5.08 s (test deadline) |
| Bytes the client sent before a 256 MB upload was rejected (curl `size_upload`) | 268,435,779 | ≤ 1,245,184 |
| `/api/health` p50, concurrency 1 | 1.64 ms | 1.11 ms |
| `POST generate → mock` p50, concurrency 1 | 9.70 ms | 10.69 ms (regression, +1.0 ms) |
| Tests | 36 unit / 17 smoke | 39 unit / 20 smoke |
