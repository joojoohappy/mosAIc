# 07 — Architecture Decision Records

Two kinds of records below. **ADR-1…6** reconstruct decisions the original authors made; the evidence is their code, comments and commit messages, and "alternatives considered" lists only what those sources mention or what the code visibly rules out. **ADR-7…10** are decisions made in this study, backed by its measurements. Nothing here claims an evaluation that was not done.

---

## ADR-1 · The prompt never leaves the server (`recipeId` in, prompt out)

- **Problem**: the recipes are other people's prompts; the API key will be billable.
- **Constraints**: unverified creators; future mobile client; keys only in backend env.
- **Alternatives (from commit `90bf3bf`)**: a convention "only read the JSON in a server component"; a denylist that drops `prompt`.
- **Decision**: client sends only `recipeId`; `public_recipe()` returns an **allowlist** of fields.
- **Trade-offs**: clients cannot show or tweak the prompt (by design); any new public field needs an explicit code change.
- **Evidence**: `PublicProjection` tests; smoke checks "list/detail omits prompt".
- **Limitation**: the "public prompt" UX described in early wireframes is not supported.

## ADR-2 · Server-authored provenance with three modes

- **Problem**: the demo must keep working when the provider fails, without lying about where an image came from.
- **Alternatives**: client-side labelling; a boolean; hiding failures behind a cached image.
- **Decision**: `mode ∈ {live, cached, mock}` + `sourceNote` written by the server, rendered verbatim; `cached` requires a complete provenance sidecar whose image passes the magic-byte check.
- **Trade-offs**: more contract surface; fallback assets need provenance work (`pregen.py`).
- **Evidence**: `Modes`, `Disclosure`, `SidecarValidation` (20 tests).
- **Would change at scale?** No — this is a product invariant; storage of the note would move to a database.

## ADR-3 · Synchronous provider call inside the request (no job queue)

- **Problem**: Build Day scope; one demo operator.
- **Alternatives (implied by the client contract: "No polling")**: async job + polling; websockets.
- **Decision**: `POST /api/generate` blocks up to the provider's duration; browser and Next proxy allow 75 s.
- **Trade-offs**: simplest possible client; but request lifetime = provider latency, so concurrency is bounded by worker threads and proxy timeouts.
- **Measured consequence**: S2 — with the original shared pool, ≥40 in-flight generations stalled every other route (ADR-7 addresses this without changing the contract).
- **Would change at scale?** **Yes.** Beyond a demo, provider p99s of tens of seconds, retries, and platform request limits (many hosts cap at 30–60 s) push towards `202 Accepted` + job id + polling/SSE and a durable queue. Not done here: it changes the public contract and the frontend, and no traffic justifies it yet.

## ADR-4 · Files on local disk for results (no database)

- **Decision**: `storage/results/{uuid}.json|png`, atomic `tmp`+`os.replace`, served by `/static`.
- **Trade-offs**: zero infrastructure; but single-host only, no retention, no listing, no multi-instance.
- **Measured**: S5 — `mock` 430 B/request; `cached` 1.5 MB/request (asset copied).
- **Would change at scale?** **Yes**: object storage for images + a small table for result metadata, with a TTL. Rejected for now because there is one host and no users.

## ADR-5 · Same-origin proxy through Next.js rewrites

- **Decision**: browser calls `/api/*`; Next rewrites to `BACKEND_URL`. No CORS anywhere.
- **Trade-offs**: simple security story; but the app cannot be statically exported, and every generation holds a Next.js proxy connection for up to 75 s.
- **Would change at scale?** Possibly: a reverse proxy (or the platform's routing) in front of both services, so the Node process is not a long-request relay.

## ADR-6 · `tryReady` gate, default false

- **Decision**: a recipe cannot be run until a human records a basis; the server enforces it (403) and the UI disables Create.
- **Evidence**: `TryReadiness` tests, startup warning.
- **Measured side effect**: the gate runs *after* the body is parsed (S1, S3) — addressed for oversized bodies by ADR-9.

---

## ADR-7 · Give generation its own capacity limiter; make health async  *(this study)*

- **Problem**: S2 baseline — at ≥40 concurrent generations `/api/health` took ~4.8 s; recipe and result pages share the same pool.
- **Constraints**: keep the HTTP contract; no new infrastructure; provider SDKs are usually blocking.
- **Alternatives considered**:
  1. Raise the default thread pool (`anyio` limiter) to, say, 200 — moves the cliff, keeps the coupling, multiplies memory (each request may hold 8 MiB).
  2. Make everything `async def` with an async provider client — the provider is not chosen; forces async I/O discipline on file code for no gain.
  3. Separate process / queue for generation — correct at scale (ADR-3) but a contract change.
  4. **Dedicated `anyio.CapacityLimiter` for `run_generation` + `async def health`.** ← chosen
- **Criteria**: isolation of read routes, bounded concurrent provider calls, diff size, contract unchanged.
- **Measurements**: see [04](04-benchmark-results.md) S2 — health latency at 40/60 in flight drops back to the no-load level; generation throughput is now capped by the limiter (8 by default), which is the intended trade-off.
- **Remaining limitations**: queued generations wait inside the request; with limiter = 8 and a 5 s provider, the 60th request waits ~37 s, so bursts above *limiter × 75 s / provider latency* will hit client timeouts. The right value is a function of the provider's rate limit, which is unknown — hence an env var, not a constant.

## ADR-8 · Bound the caller's wait for the provider in the pipeline, not in each SDK call  *(this study)*

Scope: this bounds response time and returns a fallback. It does **not** cancel provider work already started.

- **Problem**: S4 baseline — a hung provider holds the request until the caller aborts; nothing returns a result.
- **Alternatives**: rely on the future SDK's timeout (unknown, may not cover all phases: connect, upload, generation, download); `signal.alarm` (main thread only); asyncio timeout (provider is sync).
- **Decision**: run `_call_provider` in a bounded `ThreadPoolExecutor` (2 × the generation limit); `future.result(timeout=MOSAIC_PROVIDER_TIMEOUT_S)` (default 60 s, matching the documented contract); on timeout, cancel if not started and fall back with `fallbackReason="TimeoutError: provider exceeded …"`.
- **Why it is safe**: invariant 1 (provider never writes; one write after mode is decided) means an abandoned thread finishing later cannot corrupt anything — pinned by the new test `test_late_provider_result_never_reaches_disk`.
- **Trade-off**: an abandoned call keeps a thread (and possibly provider credit) until it ends; the pool size caps how many can pile up. A real SDK timeout should still be set; this is the backstop.

## ADR-9 · Reject oversized uploads at the ASGI layer  *(this study)*

- **Problem**: S3 baseline — 256 MB uploads were fully sent by the client and parsed/spooled by the server before the 400/403.
- **Alternatives**: reverse-proxy `client_max_body_size` (correct in production; no proxy exists yet); checking `Content-Length` inside the route (too late — FastAPI parses the form before the route body runs).
- **Decision**: a ~60-line pure-ASGI middleware on `POST /api/generate`: reject a declared `Content-Length` > 8 MiB + 64 KiB without reading; count streamed bytes for chunked bodies and stop at the limit. Same `400 {"error":"too_large"}` contract.
- **Trade-offs**: (a) an oversized upload to a *not-ready* recipe now answers `too_large` instead of `recipe_not_ready` (precedence change, documented); (b) when the server answers before reading the body, curl and Chromium read the 400, but Node's undici and Python's urllib surfaced a connection reset instead — acceptable because the web client validates size before sending.
- **Would change at scale?** Move the limit to the edge proxy as well; keep the middleware as defence in depth.

## ADR-10 · Decisions *not* taken (measured and rejected)

| Candidate | Measurement | Why not |
|---|---|---|
| Cache `recipes.json` in memory | `load_recipes()` = ~31 µs per call (S7); 3 recipes, 7.9 KB | Saves ~0.03 ms on a ≥1.5 ms request. Re-reading also means edits to `tryReady` take effect without restart — a feature for this team. |
| Store a reference to the fallback image instead of copying it per result | Copy = 1.5 MB/request (S5) | Copying keeps each result immutable if the fallback is regenerated; referencing would make old results' `sourceNote` describe a different image. Fix the growth with retention (TTL clean-up) instead — recorded as a gap. |
| Pin dependencies with a lock file | — | Correct, but the versions the authors ran are unknown and PyPI was unreachable here; pinning to the sandbox's source build of FastAPI would be fabricating a tested configuration. Recommended for the authors. |
| Job queue + polling | — | Contract change; see ADR-3. |
