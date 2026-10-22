# 07 · Architecture decision records

ADR-1 to ADR-6 record decisions already present in PR #2. Their "alternatives" are the ones visible in the code, comments, commit history or release docs; where the original evaluation was not written down, the ADR says so instead of inventing one. ADR-7 to ADR-10 were made in this branch, with measurements.

---

## ADR-1 · Generate synchronously inside the HTTP request

- **Problem:** a generation takes seconds to a minute (external model). The browser needs a result ID.
- **Constraints:** Vercel functions (no long-lived workers), ≤ 50 paid calls/day by default, ≤ 2 concurrent per instance, small team.
- **Alternatives:** (a) synchronous request held open up to 75 s; (b) job queue + worker + polling (`generation_id` / `status` was the original API sketch, see `docs/architecture/api-contract.md` mapping table); (c) streaming/SSE progress.
- **Criteria:** moving parts, hosting fit, failure modes, user experience.
- **Selected:** (a). `POST /api/generate` returns `{resultId}` after the model finishes or fails; timeouts are layered 60 s (provider) < 75 s (Next rewrite `proxyTimeout`) = 75 s (client `AbortSignal`).
- **Trade-offs:** no queue, broker or worker to run; but a request occupies a threadpool thread and a function invocation for the whole model call, a refresh mid-call orphans the request (now mitigated by ADR-9), and there is no progress reporting.
- **Evidence:** B2 shedding: served requests take provider time + ~0.1 s; the concurrency cap keeps held requests bounded.
- **Limitations / would change at scale:** beyond a few concurrent generations per instance, or with model times near the function limit, move to (b): enqueue, return `202 {id}`, poll or push. The `mode`/`resultId` contract already allows it.

## ADR-2 · Shed load at a fixed concurrency instead of queueing

- **Problem:** cap spend rate and memory when many people press "create" at once.
- **Alternatives:** unbounded concurrency; an in-process queue; a fixed gate with immediate 503.
- **Selected:** `Limiter.acquire()`: over `MOSAIC_MAX_CONCURRENT` (default 2) → `503 server_busy` with a clear Chinese message.
- **Trade-offs:** predictable cost and memory (B2: ~40 MB per in-flight 7.6 MB upload) and instant feedback (B2: shed responses in < 125 ms), at the price of making the user retry.
- **Evidence:** B2 `shedding`: bursts of 10 and 20 → exactly 2 served, 2 provider calls.
- **Limitation:** per process. N instances admit 2N.

## ADR-3 · No provider retries; every failure becomes a labelled fallback

- **Problem:** the model can error, refuse (text-only answer), time out or return junk.
- **Alternatives:** retry with backoff; fail with an error page; fall back to an example.
- **Selected:** zero retries; fall back to `cached` (pre-generated example with provenance) or `mock` (placeholder), with a public `fallbackReason` (`provider_timeout`, `provider_no_image`, `provider_error`). Provider output passes the same magic-byte check as uploads.
- **Criteria recorded in code:** "each retry is a paid call"; "the server does not lie" (`generation.py` invariants).
- **Trade-offs:** a transient blip costs the user a real result; but cost per click is bounded at one call and the UI never shows an example as the user's image.
- **Evidence:** B3 `provider_failures`: 500, text, non-JSON, refused → `mode=mock` with the matching reason in ≤ 0.14 s; E2E "model errors and timeouts end in an honest fallback".
- **Would change:** with real error data, a single retry on connection-level failures that provably did not reach the model (DNS, refused) would be safe; retries after the request body was sent would not.

## ADR-4 · Visitor identity from a signed web-tier header, never `X-Forwarded-For`

- **Problem:** per-visitor limits need the visitor IP, but the API sits behind the website's rewrite.
- **Alternatives:** trust `X-Forwarded-For` (forgeable); socket peer only (all visitors share the website's IP); platform `x-real-ip` only on Vercel; shared-secret header set by the web tier.
- **Selected:** `apps/web/proxy.ts` deletes client-sent `x-mosaic-*` headers, copies the platform's `x-real-ip` and adds `MOSAIC_PROXY_SECRET`; the API compares the secret in constant time (`hmac.compare_digest`). Fallbacks: `x-real-ip` on Vercel, then the socket peer ("stricter than intended, never looser"). uvicorn runs with `--no-proxy-headers`.
- **History:** added after a review found the limits could be bypassed with a forged header (commit `da9fd2e`).
- **Evidence:** `tests/test_limits.py` spoof tests, `tests/proxy.test.mjs`; B3 `rate_limits` → `[200,200,200,429,429,429]` with six different forged addresses.
- **Limitation:** a static shared secret, not a per-request signature; anyone holding it can claim any IP. Acceptable between two projects owned by one person.

## ADR-5 · One tiny storage interface; refuse to pay when storage is not shared

- **Problem:** Vercel functions have no persistent disk, so results written locally break share links, and a local budget counter resets on each cold start.
- **Alternatives:** a database; object storage; local disk.
- **Selected:** `Store` protocol (`put`/`get`) with `LocalStore` (dev, Docker) and `BlobStore` (Vercel Blob, private, served back through the API). On Vercel without Blob, `live_blocker()` returns `no_shared_storage` and no paid call is made.
- **Trade-offs:** no query capability, no atomic counters (see ADR-10), one Blob round trip per read; but zero schema, zero extra service.
- **Evidence:** `tests/test_storage.py` (fake Blob client), `test_vercel_without_blob_never_pays`; B3 `restart_recovery`: results survive SIGTERM and SIGKILL on LocalStore. **Real Blob not verified.**

## ADR-6 · Gemini over plain `urllib`

- **Problem:** `main` read `ANTHROPIC_API_KEY`, but Claude models do not output images; generation was unimplemented.
- **Alternatives considered (from PR #2 notes):** provider choice driven by image output and support for the seeds' aspect ratios (3:4, 4:5). SDK vs. raw HTTP: raw HTTP chosen because "one POST does not need an SDK".
- **Trade-offs:** no SDK retries/typing to rely on; protocol drift is caught only by `extract_image` failing (→ honest fallback, not a crash).
- **Limitation:** written from documentation, never called with a real key. This is the single biggest unverified assumption in the project.

---

## ADR-7 · Enforce the provider timeout as a wall-clock deadline (this branch)

- **Problem:** `urlopen(timeout=60)` bounds each socket operation, not the call. Measured: with a 2 s timeout, a provider that sends one byte every 100 ms held the request for **12.6 s**, and the result was even stored as `live`.
- **Alternatives:** (a) read the body in chunks and check a deadline between reads, single thread; (b) run the call in a worker thread and `join(deadline)`; (c) switch to `httpx` with its pool/read/write timeouts; (d) `signal.alarm` (main thread only, unusable in a threadpool).
- **Criteria:** strict bound for the caller, no new dependency, no change to the provider contract, small diff.
- **Selected:** (b) + (a): the caller waits at most the deadline; the worker also checks the deadline between `read1()` calls so it does not keep downloading after the caller has moved on.
- **Trade-offs:** an abandoned worker can live until its next socket read returns (≤ one per-read timeout); the upstream may still bill a call the user never sees (already counted against the daily budget, as before). `httpx` would have been cleaner but adds a runtime dependency to a deliberately small service.
- **Evidence:** B3 drip 12.6 s → 2.0 s; `tests/test_hardening.py::ProviderDeadline`.

## ADR-8 · Validate JPEG uploads by a reduced-scale decode (this branch)

- **Problem:** Pillow's `verify()` only parses JPEG headers; damaged photos reached the paid call.
- **Alternatives (measured, [`validation_alternatives.json`](../../benchmarks/results/validation_alternatives.json)):** `verify` 0.04 ms, catches nothing; end-of-image marker check 0.04 ms, catches truncation but **rejects valid photos with trailing data** (motion photos append video after the marker); full `load()` 106 ms at 12 MP; `draft()` to 1/8 scale + `load()` 48 ms at 12 MP, same detection as full decode.
- **Selected:** draft decode for JPEG, full decode for WebP (no draft mode), unchanged CRC `verify()` for PNG.
- **Trade-offs:** +13 ms per 3 MP upload; uploads on Vercel are ≤ 4 MB / 2048 px after browser resize, so the realistic worst case is the 3 MP row. Mid-file corruption is still accepted (libjpeg conceals it; so does full decode).
- **Evidence:** B3 `corrupt_uploads` 6/6 damaged reached provider → 0/6; B2 overhead before/after.

## ADR-9 · Coalesce overlapping identical requests in-process (this branch)

- **Problem:** the 10-minute duplicate cache only knows finished generations. A refresh or second click during the model call paid again (measured: 2 provider calls, 2 different results).
- **Alternatives:** client-side only (disable button, persist pending ID); server single-flight per fingerprint; shared lock in Blob (no compare-and-swap available in the code's Blob usage).
- **Selected:** `Limiter.lead(key)`: first request runs; identical ones wait (≤ 75 s, at most 8 waiters in total) and return the same `resultId`. A waiter whose leader ended without a result runs on its own.
- **Trade-offs:** waiting requests hold threadpool threads (capped by `MAX_WAITERS` and the per-visitor rate limit, which still counts them); only works within one instance.
- **Evidence:** B3 duplicates: simultaneous and 1 s-apart cases 2 → 1 provider call; `tests/test_hardening.py::OverlappingDuplicates`.

## ADR-10 · Do not make the daily budget counter atomic across instances (this branch, decided against)

- **Problem:** the global budget is a read-modify-write of a JSON object. Several processes lose increments (B3 `budget_race`), so the daily cap can be exceeded.
- **Alternatives:** file lock (`fcntl`) for LocalStore only; conditional writes (ETag) on Blob, not used by the current SDK calls; a database or Redis with atomic `INCR`; rely on the provider's own spend cap.
- **Selected:** fix only the crash (unique temp names: the collision produced HTTP 500s after paid calls, sometimes discarding a paid image), correct the docstring that claimed a bounded overshoot, and keep the provider-side spend cap as the hard guard (already step 1 of the release checklist).
- **Why not more:** the deployed shape (Vercel + Blob) cannot be fixed with a file lock, the local multi-worker shape is not used by Docker or Vercel, and adding Redis to protect a $54/month ceiling is more infrastructure than the problem justifies.
- **Would change:** at higher volume or real revenue, move counters to a store with atomic increments and make the limiter shared too.

---

## Decisions that would change at substantially larger scale

| Today                                                | At scale                                                                             |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Synchronous request (ADR-1)                          | Queue + workers, `202` + polling or push                                             |
| In-memory per-instance limits, dedupe, single-flight | Shared store (Redis or the database) with atomic ops                                 |
| Daily budget as a JSON blob (ADR-10)                 | Atomic counter; per-tenant quotas                                                    |
| `recipes.json` read per request                      | Database or cached, versioned content                                                |
| Static shared secret between tiers (ADR-4)           | Signed, expiring per-request tokens, or the platform's private networking            |
| Plain-text logs                                      | Structured logs with request IDs, metrics (latency, fallback rate, spend), alerts    |
| One model provider, no retries                       | Provider abstraction with health-based routing; retries only before the body is sent |
