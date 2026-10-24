# 05 · Engineering improvements

Four changes, each chosen because a benchmark showed a gap between what the code promised and what it did. Each has a regression test in [`apps/backend/tests/test_hardening.py`](../../apps/backend/tests/test_hardening.py) that fails on PR #2's code ([`regression_tests_on_baseline.log`](../../benchmarks/results/regression_tests_on_baseline.log)) and passes here ([`regression_tests_on_branch.log`](../../benchmarks/results/regression_tests_on_branch.log)). Full suite after the changes: [`test-all-after.log`](../../benchmarks/results/test-all-after.log).

Selection criteria, in order: does it change cost or correctness for a user; is it measurable; is the diff small and local; does it preserve the architecture (no new services or runtime dependencies).

## Summary

| #   | Problem (measured on PR #2)                                                                                            | Change                                                                                               | Result (after)                                                                                        | Cost                                          |
| --- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| 1   | JPEG truncated to 1 % passed validation; 6/6 damaged JPEGs reached the paid call                                       | Reduced-scale decode (`draft` + `load`) for JPEG, full decode for WebP                               | 5/6 rejected with 400 before the provider; the 6th (mid-file zeros) is also accepted by a full decode | +13.7 ms p50 per 3 MP upload, +52 ms at 12 MP |
| 2   | "60 s deadline" bounded each socket read; slow drip held a 2 s timeout for 12.63 s and stored the result as `live`     | Wall-clock deadline: call in a worker thread joined for the deadline; worker checks it between reads | 2.07 s, `provider_timeout`                                                                            | One extra thread per model call               |
| 3   | Overlapping identical requests (refresh/second click during the model call) each paid                                  | In-process single-flight per fingerprint (`Limiter.lead/done`)                                       | 2 → 1 provider call, same `resultId`                                                                  | Waiting requests hold a thread (capped at 8)  |
| 4   | Two processes writing the same `LocalStore` file collided on a fixed temp name: HTTP 500s, sometimes after a paid call | Unique temp name per write; Blob read errors go to `logging` instead of `print`                      | 6 → 0 HTTP 500s in 5 trials × 4 workers                                                               | None measurable                               |
| 5   | Chunked oversized body answered with FastAPI's generic `400 {"detail": ...}` instead of `413 too_large`                | Middleware answers 413 itself, then gives the app a synthetic disconnect                             | 413 `too_large` with and without `Content-Length`                                                     | None measurable                               |

Plus one documentation correction: `limits.py` claimed the global budget could overshoot by at most `MAX_CONCURRENT` per instance. Measured: 73 calls against a limit of 50 with 4 workers (bound would be 58). The docstring now says what is true and why the provider-side spend cap is required.

## 1 · Upload validation that actually decodes JPEGs

**Original problem.** `validate_upload` ran `Image.verify()`. For PNG that checks every chunk CRC; for JPEG it only parses headers. [`compare_validation.py`](../../benchmarks/compare_validation.py) showed a 3 MP JPEG cut to 99, 90, 50, 10 and 1 % all passed; B3 confirmed each reached the provider. The existing test cut the file to 40 bytes, which fails at `Image.open` before verify runs, so it could not catch this.

**Why it matters.** A truncated upload (mobile connection drop, broken client resize) costs a paid model call and returns either an error or a broken image.

**Alternatives (measured, [`validation_alternatives.json`](../../benchmarks/results/validation_alternatives.json)):**

| Method                      | 3 MP cost | 12 MP cost | Truncations caught | Valid + trailing bytes        |
| --------------------------- | --------- | ---------- | ------------------ | ----------------------------- |
| `verify()` (PR #2)          | 0.04 ms   | 0.04 ms    | 0 / 5              | accepted                      |
| end-of-image marker `FF D9` | 0.03 ms   | 0.04 ms    | 5 / 5              | **rejected** (false positive) |
| `draft()` 1/8 + `load()`    | 13.2 ms   | 48.3 ms    | 5 / 5              | accepted                      |
| full `load()`               | 22.8 ms   | 105.7 ms   | 5 / 5              | accepted                      |

The marker check is the tempting cheap answer, but phones append data after the image (motion photos embed a video), so it would reject real photos. Draft decoding still makes libjpeg read every compressed byte but skips most of the inverse DCT, giving the same detection as a full decode at about half the cost. None of the methods catches 20 KB of zeros in the middle; libjpeg conceals that, and so would a model.

**Implementation.** [`generation.py`](../../apps/backend/app/generation.py) `validate_upload`: PNG keeps `verify()`; JPEG uses `draft("RGB", (w/8, h/8))` then `load()`; WebP uses `load()`. The pixel-count check (decompression-bomb guard) still runs before any decode.

**Before → after.** Damaged JPEGs reaching the provider 6/6 → 1/6. MOSAIC's own generate latency p50: 0.3 MP 8.7 → 11.2 ms, 3 MP 25.2 → 38.9 ms, 12 MP 79.9 → 132.3 ms. **This is a latency regression, kept on purpose**: it is < 1 % of a request that waits seconds for the model, and it replaces a paid call with a free 400.

## 2 · A real deadline for the model call

**Original problem.** `urllib.request.urlopen(req, timeout=60)` sets the socket timeout per operation. An upstream that sends a byte now and then never trips it. With `MOSAIC_PROVIDER_TIMEOUT=2` and the fake provider dripping 1 byte / 100 ms, the request took 12.63 s, and because the bytes eventually formed an image, it was stored as `live`. With the production setting of 60 s the same pattern could hold a request, one of only two concurrency slots, and a serverless invocation for far longer than 60 s.

**Alternatives.** Chunked reads with a deadline check only (simple, but a fully stalled read still waits a whole socket timeout); a worker thread joined with a timeout; replacing `urllib` with `httpx` (better timeout model, new runtime dependency); `signal.alarm` (main thread only, unusable in a threadpool). See [ADR-7](07-architecture-decisions.md).

**Implementation.** [`provider.py`](../../apps/backend/app/provider.py): `generate()` starts the request in a daemon thread and `join`s it for the deadline; if it is still running, it raises `TimeoutError` (→ `provider_timeout`). The worker reads with `read1()` and checks the deadline between reads, so an abandoned call stops at its next read. `generation.py` already guaranteed that a late provider thread cannot write anything (all writes happen in `_write_result` after the mode is decided), which made this safe.

**Before → after.** Slow drip: 12.63 s / `live` → 2.07 s / `provider_timeout`. Hang 5 s: 2.10 → 2.08 s (unchanged, already worked). Healthy calls: 0.15 → 0.14 s.

## 3 · Overlapping duplicate requests pay once

**Original problem.** Duplicate protection looked up `recent_result(fingerprint)`, which is filled only after a generation finishes. The E2E test "refreshing during generation and trying again does not pay twice" waits 3.5 s for a 3 s fake model before retrying, so it never overlapped the two requests. B3: simultaneous and 1 s-apart duplicates each made 2 provider calls and produced 2 different results. With a real model taking 10–60 s, a refresh during that window is the common case.

**Alternatives.** Client-side only (the button is already disabled while busy, but a refresh resets the page); server single-flight; a shared lock in Blob (needs compare-and-swap the current Blob usage does not provide). See [ADR-9](07-architecture-decisions.md).

**Implementation.** [`limits.py`](../../apps/backend/app/limits.py) `Limiter.lead(key)` returns `lead`, `waited` or `bypass`; [`main.py`](../../apps/backend/app/main.py) runs the generation for the leader and calls `done(key)` in a `finally`. Waiters block up to 75 s, then return the leader's `resultId`; if the leader ended without one (busy, budget, error) the waiter is handled on its own. At most 8 requests wait at once; beyond that they take the normal path (usually a quick 503). Waiters still pass the per-visitor rate limit first, as before, so this adds no new way to occupy threads beyond what the limits allow.

**Before → after.** Simultaneous: 2 → 1 provider call; 1 s apart: 2 → 1; after completion: 1 → 1. All three return the same `resultId`.

**Limitation.** Per process. Two Vercel instances receiving the two requests would still both pay.

## 4 · No more HTTP 500s from concurrent local writes

**Original problem.** `LocalStore.put` wrote to `<name>.tmp` then `os.replace`d it. Within one process the budget's lock serialised writes; across worker processes two writers shared the temp path and one `os.replace` failed with `FileNotFoundError`. In the 4-worker budget race this produced 6 HTTP 500s over 5 trials. When it happened in `budget.record("live")` _after_ a successful paid call, the broad `except` in `run_generation` turned the paid live image into a fallback.

**Implementation.** [`storage.py`](../../apps/backend/app/storage.py): temp name `<name>.<uuid>.tmp`. Also replaced a `print` in `BlobStore.get` with `logging`, so Blob read failures appear in the same log stream as everything else.

**Before → after.** HTTP 500s: 6 → 0 over 5 trials, each with 4 workers (earlier drafts called this "20 trials"); provider-call overshoot remains (51–53 for a limit of 50) by decision ([ADR-10](07-architecture-decisions.md)).

## 5 · Chunked oversized bodies return the documented error (follow-up)

Carried over from the earlier, now-reverted case study on the pre-v0.1 backend (PR #4), where the same middleware bug was found and fixed.

**Problem.** `BodySizeLimit` raised an exception from `receive()` when a chunked body crossed the cap. FastAPI's form parsing caught it and answered `400 {"detail": "There was an error parsing the body"}`. The status was close, but the body was wrong: the web client maps the error **code** to its message, so this would show "request failed" instead of "photo must be under 8 MB". Browsers send `Content-Length`, so this mostly affects non-browser clients, but the contract should hold for every client.

**Change.** When the cap is crossed, the middleware now sends `413 {"error":"too_large"}` itself, hands the app a synthetic `http.disconnect`, and drops anything the app tries to send afterwards.

**Evidence.** The new unit test `ApiLimits.test_body_cap_rejects_chunked_upload_with_the_contract_error` failed before the change (`(400, {'detail': ...})`) and passes after. Against a real uvicorn server, a 20 MB upload returned `413 too_large` both with `Content-Length` and with `Transfer-Encoding: chunked`. The HTTP smoke test still passes 18/18.

## Regression check

| Check                         | Before             | After                              |
| ----------------------------- | ------------------ | ---------------------------------- |
| Backend unit tests            | 73 pass            | 84 pass (85 with follow-up §5)     |
| HTTP contract (`test_api.sh`) | 18/18              | 18/18                              |
| Node client/upload/proxy      | 19/19              | 19/19                              |
| Production build              | pass               | pass                               |
| Playwright journey + quality  | 13/13              | 13/13                              |
| Read endpoints p50 (c=1)      | 0.66–1.02 ms       | 0.60–1.05 ms                       |
| Load shedding (burst 10/20)   | 2 served, rest 503 | identical                          |
| Memory, 16 in flight          | 535 MB             | 493 MB (noise; no change targeted) |

## Considered and not implemented

| Idea                                                               | Evidence                                                                                          | Why not                                                                                                                                    |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Cache `recipes.json` in memory                                     | `load_recipes` is 0.05 ms of a ~1 ms request; `/api/recipes` already serves ~900 req/s per worker | Saves almost nothing; adds staleness                                                                                                       |
| Profile/speed up FastAPI response encoding for recipe/result reads | ~1 ms CPU per read at saturation                                                                  | No user-visible need at this traffic; Blob latency will dominate on Vercel                                                                 |
| Cross-process atomic budget (file lock, Redis)                     | 51–53 calls vs 50 with 4 local workers                                                            | File lock does not help on Vercel+Blob; Redis is new infrastructure for a $54/month ceiling; provider spend cap is the real guard (ADR-10) |
| Reduce per-request memory (stream base64 into the request body)    | ~30–44 MB per in-flight 7.6 MB upload                                                             | Bounded by `MAX_CONCURRENT=2` (~140 MB); real uploads on Vercel are ≤ 4 MB                                                                 |
| Retries for provider errors                                        | —                                                                                                 | Each retry is a paid call; no real failure data to tune them on                                                                            |
| Container `HEALTHCHECK`, non-root user                             | B4: neither present                                                                               | The Docker image is for local verification; production is Vercel. Worth adding if Docker becomes a deploy target                           |
| Structured logging / metrics                                       | Logs are one plain line per generation                                                            | Valuable, but the right shape depends on where logs go on Vercel; listed in [06](06-production-readiness.md)                               |
