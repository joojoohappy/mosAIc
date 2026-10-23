# 09 — Resume and Hiring Review

Written as a sceptical senior interviewer who has read the repo, `git log`, and this case study.

## 0. The first thing an interviewer will check: who wrote what

| Area | Author per `git log` |
|---|---|
| Build Day plan, initial scaffold, PR merge | `joojoohappy` (5 commits) |
| FastAPI backend, tests, monorepo restructure, Docker (co-authored with Claude) | Zoe Wu (10 commits) |
| Next.js frontend + workspace migration | Codex agent (1 commit, merged by `joojoohappy`) |
| This study: audit, benchmark harness, reliability fixes, CI file | this case-study branch |

If you present the backend design as yours and you are not Zoe Wu, an interviewer who opens the history will stop trusting everything else. If Zoe Wu *is* you (a second identity), say so up front. The scores below assume the defensible framing: **you owned the product and contract, directed AI coding agents, integrated their output, and personally ran the reliability audit and fixes in this study.**

## 1. Scores (1 = weak, 5 = strong)

| Criterion | AI Eng | ML Eng | ML Infra | AI Platform | SWE | Solutions Eng/Arch |
|---|---|---|---|---|---|---|
| Technical relevance | 3 | 1 | 3 | 4 | 3 | 4 |
| System design complexity | 2 | 1 | 3 | 3 | 3 | 3 |
| Engineering ownership | 2 | 1 | 3 | 3 | 2 | 3 |
| Measurable outcomes | 2 | 1 | 4 | 4 | 3 | 3 |
| Production engineering maturity | 2 | 1 | 2 | 2 | 2 | 2 |
| Differentiation | 3 | 1 | 3 | 3 | 2 | 4 |
| **Total / 30** | **14** | **6** | **18** | **19** | **15** | **19** |

Evidence behind the scores:

- **Relevance**: the system is the *serving shell* around an external image model — timeouts, fallbacks, concurrency, provenance, trust boundaries. That is squarely AI-Platform / Infra / Solutions territory. It has no training, data, evaluation or inference — hence ML Engineer = 1 across the board.
- **Complexity**: ~330 lines of backend logic and ~200 of client logic. The ideas are good; the scale is small. Complexity rises to 3 for infra roles only because of the concurrency analysis.
- **Ownership**: limited by authorship (§0). The study's fixes are a real, attributable contribution.
- **Measurable outcomes**: before/after numbers exist for three reliability properties (S2–S4), reproducible from `benchmarks/`. No model metrics exist, so AI/ML roles score low.
- **Maturity**: no provider, no deployment, no observability, CI only one run old — 2 everywhere.
- **Differentiation**: the provenance contract ("never present a cached image as yours", server-authored disclosure, consistency-checked provenance sidecars) is unusual and makes a memorable story for Solutions and AI-product roles. Generic CRUD + Next.js scores 2 for SWE.

## 2. Resume bullets (only verified numbers)

1. **Load-tested a FastAPI generation service and removed a head-of-line failure**: with ≥40 concurrent slow (simulated, 5 s) model calls, the shared 40-thread pool stalled `/api/health` from ~3 ms to ~4.8 s; isolating generation behind a dedicated AnyIO capacity limiter kept health at 2–11 ms with 60 generations in flight (2 ms with tiny uploads, ≤ 11 ms with 1.6 MB photos) (reproducible benchmark, 3 trials per load level).
2. **Bounded response time for a (simulated) external model call** with a labelled fallback (bounded executor, cancel-if-not-started, abandoned calls never write — pinned by a test): against a provider that never returns, the caller now gets a fallback result in 5.1 s at the test setting (60 s default) instead of waiting until it aborts. The started call is not cancelled.
3. **Enforced upload limits at the ASGI layer**, before multipart parsing: a 256 MB request went from fully sent and parsed (268 MB, ~0.7 s on loopback) to rejected in ~1 ms with < 1.3 MB sent by the client, keeping the documented `too_large` error contract (verified with curl and Chromium).
4. **Defined the product and API contract for a provenance-first AI image app** (live / cached / mock results with server-authored disclosure; prompts never leave the server) and integrated a FastAPI backend with a Next.js client produced with AI coding agents; contract covered by 39 unit, 20 HTTP-contract and 5 real-HTTP tests.
5. **Built a reproducible benchmark harness** (isolated server copies, labelled test doubles, zero-dependency load generator, before/after runs against a `git archive` baseline) and documented ADRs, including improvements measured and rejected.

Bullets 1–3 describe work done in this study; keep them only if you can explain them yourself (see §3).

## 3. Interview talking points and the hard follow-ups

**Thread-pool cliff (bullet 1)**
- *Why exactly 40?* AnyIO's default `CapacityLimiter` for `to_thread.run_sync` is 40; Starlette runs every sync `def` route through it.
- *Why not just raise it to 500?* Memory (each generation can hold 8 MiB), provider rate limits, and it only moves the cliff.
- *What happens to request 61 now?* It waits for a slot inside the request. With 8 slots and a 5 s provider, 60 requests took ~40 s — bursts beyond `slots × 75 s / latency` will hit client timeouts. The real fix at scale is async jobs (ADR-3).
- *Is health being fast actually useful if generation is queued?* It is: the client uses health to decide "backend down" vs "slow"; a false "down" is worse UX than a slow spinner.

**Bounded wait (bullet 2)**
- *You can't kill a Python thread — so what happens to the abandoned call?* It runs to completion in the pool; the pool is 2 × the limit; the call can't write (invariant + test). Real SDK timeouts are still needed.
- *Does the user still get billed?* Possibly — abandoned calls may complete at the provider. Measure with the real provider.

**Upload guard (bullet 3)**
- *Why not nginx `client_max_body_size`?* Should exist in production too; there is no proxy yet, and defence in depth is cheap.
- *What do clients see on the early 400?* curl and Chromium read it; Node's undici and Python's urllib saw a reset. The web client validates size before upload, so only non-browser clients see the reset.
- *What changed in behaviour?* Oversized + not-ready now returns `too_large` instead of `recipe_not_ready`.

**Provenance design (bullet 4)**
- *Why server-authored text instead of a UI label from `mode`?* One source of truth for a claim with legal/ethical weight; the client also rejects inconsistent payloads.
- *Where does that break at scale?* Results on local disk; no retention; the fallback copy costs 1.5 MB per request.

**Questions you must be ready to answer honestly**
- "What model did you use and what was its latency/cost?" → None yet; the provider is unimplemented. Explain why that was the right call for the project's honesty rule, and what you would measure first.
- "Did you write the backend?" → §0.
- "Has this run in production or CI?" → Not in production. CI: yes, green on PR #4.

## 4. Weaknesses

- **Overclaims to avoid**: "AI pipeline", "model serving", any model metric, "production", the original docstring's "health stays responsive" as an unconditional property.
- **Engineering gaps**: no provider; frontend unverified here and without tests; a CI history of a single run; unpinned Python deps; no logs/metrics; no rate limiting; unbounded result storage; Docker is `next dev`.
- **Not yet impressive**: S1 throughput numbers (loopback, 2 vCPU, no model); the monorepo structure; the UI.

## 5. Final verdict

**Not yet competitive as a stand-alone international AI/ML case study.** It is a credible **supporting** project for AI Platform, ML Infra and Solutions roles *if* told honestly, because it shows judgement about serving an unreliable external model and contains measured, reproducible reliability work.

What is missing, precisely:

1. **A real provider integration** with measured latency distribution (p50/p95/p99 over ≥100 calls), failure rate, timeout rate, and **cost per successful generation**.
2. **A simple output-validity / quality check** (e.g., format/aspect-ratio compliance with the recipe, refusal rate) — the first AI-specific evaluation.
3. **A deployed instance** (even a small VM) with structured logs (request id, mode, fallback reason, provider latency) and one dashboard.
4. ~~CI that has run green~~ (done: PR #4), plus one browser E2E test of Discover → Create → Result.
5. **Unambiguous personal ownership** of at least one of the above.

Items 1–2 turn it from "serving shell" into an AI system; 3–4 turn "validated prototype" into "production-oriented". With those, re-score: AI Platform/Infra would move to ~24/30.
