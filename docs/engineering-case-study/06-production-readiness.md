# 06 — Production Readiness

## Classification: **Validated Prototype**

Scale used: Prototype → **Validated Prototype** → Production-Oriented → Production-Ready → Production-Deployed.

MOSAIC is past "prototype": its backend contract is specified, tested at three levels (unit, HTTP contract, real-wire integration) and re-verified here, and its reliability behaviour under load has now been measured and partly hardened. It is **not** production-oriented: the core feature (AI generation) does not exist, nothing is deployed, nothing is observed, and nothing enforces the tests on every change.

Passing local tests is not treated as evidence of readiness; each row below names what *would* be evidence.

| Dimension | State | Evidence | What production would require |
|---|---|---|---|
| **Core functionality** | ❌ Missing | `_call_provider` → `NotImplementedError`; all `tryReady: false` | A selected provider, implemented and measured with `pregen.py` |
| **Reliability** | 🟡 Designed + partly hardened | Fallback model (20 tests); after this study: provider deadline, isolated generation pool, upload guard (S2–S4 before/after) | Real provider failure data; retries for *idempotent* reads only; load test with real provider latencies |
| **Deployability** | 🔴 | Dockerfiles self-described as "verification-only"; web container runs `next dev`; compose needs a local `.env`; not verified here | Production `next build` image, backend image with pinned deps, health checks in compose/orchestrator, a documented deploy target that allows ≥75 s requests |
| **Configuration** | 🟡 | `BACKEND_URL` validated at Next start-up (rejects credentials/paths); backend env via `.env`; new knobs `MOSAIC_PROVIDER_TIMEOUT_S`, `MOSAIC_MAX_CONCURRENT_GENERATIONS` | Pinned Python deps (F6); config documented in one place; secrets from a manager, not files |
| **Error recovery** | 🟢 for the contract | 7 error codes mapped end-to-end; client distinguishes down / timeout / failed; no retry of non-idempotent generate | Provider-specific error taxonomy; alerting |
| **Security** | 🟡 | Prompt allowlist, magic-byte checks, id validation, path-escape checks, no CORS, keys server-side, upload size now enforced before parsing | Rate limiting / abuse controls (generation will cost money per call); auth if collections ship; retention policy for results; dependency scanning; Terms/Privacy (README notes none exist) |
| **Observability** | 🔴 | `print()` per fallback; uvicorn access log | Structured logs with request id + `mode` + `fallbackReason` + provider latency; metrics (generation latency histogram, fallback rate, queue wait); dashboards/alerts |
| **Operational complexity** | 🟢 low | Two processes, files on disk | Stays low until multi-instance (then: shared storage, ADR-4) |
| **Performance** | 🟢 for current scope | Non-generation endpoints p50 1.1–1.9 ms at concurrency 1 on 2 vCPU (S1); cold start ~0.4 s (S6) | Measurements with a real provider; frontend web-vitals (not measured) |
| **Cost predictability** | ❌ Unknown | No provider → no unit cost | Cost per generation from `pregen` runs; per-IP/global generation caps (the new limiter bounds concurrency, not spend) |
| **Test coverage** | 🟡 | Backend: 39 unit + 20 contract checks; client: 9 + 5 wire. Frontend: none in repo | CI on every PR (workflow added; [first run green](https://github.com/joojoohappy/mosAIc/actions/runs/39916292304)); frontend E2E for the core journey; coverage report |

## Blocking issues before any public deployment

1. A provider, with its own timeout, cost per call and failure modes measured.
2. A real deployment artefact (production build), pinned dependencies, and CI that has actually run green.
3. Abuse controls on `POST /api/generate` (rate limit, concurrency already bounded) — the endpoint will spend money.
4. Result retention (S5: 1.5 MB per `cached` request, unbounded).
5. Minimal observability: request id, mode, fallback reason, provider latency.

## What is genuinely production-grade already

- The provenance contract and its enforcement on both sides.
- The trust boundaries (prompt confidentiality, magic-byte header checks, id validation).
- The client's failure classification and the "never auto-retry generation" rule.

These are the parts worth showing; the rest is honest scaffolding.
