# 02 · Engineering value assessment

Perspective: a senior interviewer for AI/ML platform and backend roles, reading the repository rather than the README. Only capabilities present in code are assessed. Categories: **A** strong portfolio evidence · **B** potentially valuable, needs validation · **C** ordinary implementation · **D** unsupported claim.

## Summary

| #   | Highlight                                                                                                         | Category                                 | Roles that care most                |
| --- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | ----------------------------------- |
| H1  | Cost and abuse control for a paid model API                                                                       | **A**                                    | AI Platform, Backend/SWE, Solutions |
| H2  | Failure semantics: deadline, no retries, labelled fallbacks, untrusted model output                               | **A** (after this branch's deadline fix) | AI Engineer, AI Platform            |
| H3  | Measurement-driven hardening (this branch: 4 defects found by benchmarks, fixed, re-measured)                     | **A**                                    | All engineering roles               |
| H4  | Trust boundaries across two tiers (signed visitor IP, server-side prompts, allowlist projection)                  | **A−**                                   | SWE, Security-minded platform roles |
| H5  | Serverless-aware design (Blob storage, 4.5 MB body limit, aligned timeouts, refuse-to-pay without shared storage) | **B**                                    | Solutions Architect, Platform       |
| H6  | Gemini image-generation integration                                                                               | **B** (never run against the real API)   | AI Engineer                         |
| H7  | Test pyramid + CI (unit, HTTP contract, typed client, Playwright, axe, audits)                                    | **B+**                                   | SWE                                 |
| H8  | Read API performance                                                                                              | **C**                                    | —                                   |
| H9  | Docker / compose                                                                                                  | **C**                                    | —                                   |
| H10 | "AI system", "model orchestration", "inference optimization", "ML infrastructure"                                 | **D**                                    | —                                   |

## H1 · Cost and abuse control for a paid model API — A

- **Problem:** every click spends money (~$0.036/image per PR #2's price estimate) at a public, anonymous URL.
- **Why it is meaningful:** four independent controls with different failure domains: per-visitor window and daily cap (`limits.py`), a global daily budget reserved _before_ the call and stored in shared storage, a concurrency gate that sheds load, and duplicate suppression by content hash. Unverified recipes and missing shared storage both short-circuit before any spend.
- **Alternatives:** an API gateway's rate limiting; provider-side quotas only; user accounts.
- **Trade-offs:** in-memory limits are per instance; the shared budget is approximate across processes (measured, ADR-10).
- **How to measure:** paid calls per scenario vs. configured limits.
- **Evidence:** B3: forged `X-Forwarded-For` ×6 → 3 allowed; budget 5 → exactly 5 calls; 1-worker budget race 5/5 trials exact at 50; overlapping duplicates 2 → 1 call after ADR-9. Weakness measured too: 4 workers overshoot.
- **Interview value:** high. It is a concrete answer to "how do you put an LLM/image API on the public internet without a surprise bill?"

## H2 · Failure semantics for an external model — A

- **Problem:** the model can be slow, down, refuse, or return non-images; the UI must never show a fallback as the user's result.
- **Meaningful because:** invariants are written down and enforced in one place (`generation.py`): only `_write_result` touches storage, `live` requires real image bytes (magic-byte check on provider output), user photos are never stored, failures map to public reason codes while details stay in logs.
- **Alternatives:** retries with backoff; error pages.
- **Trade-offs:** no retries means transient failures cost a result (ADR-3).
- **Evidence:** B3 `provider_failures` (7 simulated modes); E2E fallback test. Before this branch, the "60 s deadline" was per socket read (12.6 s for a 2 s setting under slow drip) and the drip case was stored as `live`; after: 2.0 s, `provider_timeout`.
- **Caveat:** all failure modes are simulated. Real Gemini 429/quota responses were not observed.

## H3 · Measurement-driven hardening — A

- **Problem:** documented guarantees ("content decode", "never pays twice", "60 s deadline", "bounded overshoot") were not all true.
- **What was done:** a reproducible harness (fake provider, k6, `/proc` sampling, git-worktree baseline) found four defects, each fixed with a regression test that fails on PR #2's code and passes here, then re-measured. See [04](04-benchmark-results.md), [05](05-engineering-improvements.md).
- **Why it is resume-worthy:** it shows the habit interviewers probe for: verify claims, quantify, fix, prove no regression, and decide _not_ to fix when cost exceeds value (ADR-10, recipe caching).

## H4 · Trust boundaries — A−

- Server-side prompt lookup by `recipeId` (the API key cannot be used for arbitrary prompts); allowlisted public fields; body cap before multipart parsing; ID regex before any path or blob name; visitor IP signed by the web tier (ADR-4); no CORS by design.
- **Evidence:** unit tests for each; B3 `rate_limits`, `body_limits`.
- **Why not A:** static shared secret; no security headers review; prompt-injection surface not assessed against a real model (images can carry text instructions).

## H5 · Serverless-aware design — B

Sensible, documented choices (ADR-5, browser-side resize to fit the 4.5 MB limit, timeouts 60/75/75 s, `no_shared_storage` guard). **Not validated on the real platform:** previews are behind Deployment Protection, no Blob store is connected, production still serves `main`. Becomes A after one verified staging run.

## H6 · Gemini integration — B

`provider.py` builds the Interactions API request (prompt + base64 photo + aspect ratio) and parses two documented response shapes. It is small and careful, but **has never received a real response**. As a portfolio item it is "integrated against documentation", which an interviewer will discount until there is one recorded live call with latency and cost.

## H7 · Tests and CI — B+

~120 automated checks across Python and Node (134 after this branch), Playwright against the real backend with a fake model, accessibility on 12 routes × 2 widths, dependency audits, CI on every push. Weaknesses this audit found: the truncation test cut the file at 40 bytes (header-level failure, not the decode path), and the refresh E2E test waited for the first request to finish, so neither caught the real defect. Good breadth; edge-case depth was the gap.

## H8 · Read API performance — C

~900–2,500 req/s on one worker on loopback for tiny JSON payloads. Normal for FastAPI; nothing was optimised and nothing needed to be. Useful only as a baseline and as evidence of not optimising prematurely.

## H9 · Docker — C

Two simple images and a compose file for local verification; the web image runs `next dev`. No healthcheck, runs as root (B4). Not production container work.

## H10 · Claims to avoid — D

The repository does **not** contain: model training or fine-tuning, model conversion, local inference, GPU use, model serving, batching, agents, multi-step orchestration, RAG, vector stores, evaluation of output quality, or MLOps pipelines. Calling MOSAIC an "ML infrastructure" or "inference optimization" project would fail the first follow-up question. Your model-conversion experience is real, but this project is not evidence of it.
