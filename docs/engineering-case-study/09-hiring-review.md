# 09 · Hiring review

Written as a skeptical senior interviewer who has read the repository, its git history and [04](04-benchmark-results.md). Scores 1–5.

## 0. The first thing an interviewer will check: who wrote it

The repository is public and `git log` is the first stop. On the PR #2 branch: 5 commits by the owner (product specs, wireframes, scaffold, a merge), 10 by a collaborating engineer (backend architecture, tests, monorepo layout), 1 by Codex (web front end), 9 by Claude Code (Gemini integration, limits, storage, CI, E2E). This case study's code was also produced by Claude Code under the owner's direction.

That is not disqualifying; AI-assisted engineering is normal now. It changes what can be claimed. "I built the backend" will not survive the second question. "I specified, directed and reviewed an AI-assisted build, and I can explain every trade-off in it" can, **if it is true in the interview**. The scores below assume the candidate can defend the decisions in [07](07-architecture-decisions.md) without notes. If not, every "ownership" score drops to 1.

## 1. Scores by role

| Criterion                       | AI Eng | ML Eng | ML Infra | AI Platform | SWE    | Solutions Eng/Arch |
| ------------------------------- | ------ | ------ | -------- | ----------- | ------ | ------------------ |
| Technical relevance             | 3      | 1      | 1        | 3           | 3      | 4                  |
| System design complexity        | 2      | 1      | 1        | 2           | 2      | 3                  |
| Engineering ownership           | 2      | 2      | 2        | 2           | 2      | 3                  |
| Measurable outcomes             | 3      | 1      | 2        | 3           | 3      | 3                  |
| Production engineering maturity | 2      | 1      | 2        | 2           | 3      | 2                  |
| Differentiation                 | 3      | 1      | 1        | 3           | 2      | 3                  |
| **Total / 30**                  | **15** | **7**  | **9**    | **15**      | **15** | **18**             |

### Evidence behind the scores

- **AI Engineer (15).** Relevant: integrating a generative model with cost, failure and trust controls is exactly what many "AI engineer" roles do. Weak: one REST call, never executed for real; no evaluation of output quality, no prompt work beyond storing creators' prompts, no comparison of models. The honest-fallback design and server-owned prompts are good talking points.
- **ML Engineer (7).** No training, data pipelines, features, evaluation or model artefacts. Not evidence for this role. Use your model-conversion work instead.
- **ML Infrastructure (9).** No model serving, GPUs, batching or scheduling. The benchmarking discipline (fixed workloads, warm-up, repetitions, client calibration, baseline worktrees) transfers; the system does not.
- **AI Platform (15).** Cost guards, rate limits, load shedding and provider-failure handling for a paid model API are platform concerns. Limited by single-provider scope, per-instance limits, no observability, no real traffic.
- **Software Engineer (15).** Solid small-service engineering: clear invariants, ~134 automated checks, CI, measured defects with regression tests. But small (≈1 k lines of backend), little concurrency beyond a threadpool, no data model.
- **Solutions Engineer / Architect (18).** Best fit. The material is about fitting a product into platform constraints (serverless limits, storage, timeouts, cost ceilings) and documenting trade-offs for a non-specialist owner. The ADRs and readiness assessment read like solution design.

## 2. Resume bullets

Only verified outcomes; each figure is in [04](04-benchmark-results.md). Wording reflects the ownership described above; change "led"/"directed" to "built" only for parts you wrote yourself.

1. **Directed and reviewed the v0.1 backend for a public image-generation gallery (FastAPI, Next.js, Google Gemini API), defining four cost controls (per-visitor limits, global daily budget, concurrency gate with load shedding, content-hash de-duplication) that held a simulated burst of 20 requests to exactly 2 paid model calls.**
2. **Designed a reproducible reliability benchmark (fake model server, k6, git-worktree baselines) that exposed 4 defects contradicting the documented behaviour; fixed each with a regression test, cutting a slow-upstream timeout from 12.6 s to 2.1 s, duplicate paid calls from 2 to 1, and damaged uploads reaching the paid API from 6/6 to 1/6.**
3. **Chose decode-based JPEG validation over a cheaper end-marker check after measuring both (same detection as a full decode at ~half the CPU; the marker check rejected valid motion photos), accepting a +13.7 ms per-upload cost to stop paying for truncated uploads.**
4. **Documented 10 architecture decisions and a production-readiness assessment, including a measured decision _not_ to build a cross-instance atomic budget counter (overshoot 51–53 calls vs a limit of 50 across 4 workers) in favour of a provider-side spend cap.**

Do not write: "built an AI platform", "optimized inference", "reduced latency by X %" (latency went _up_ by design), "served N users" (none yet), or any Gemini latency or cost figure (never measured).

## 3. Interview talking points and the follow-ups to expect

| Topic                   | What to say                                            | Hard follow-up questions                                                                                                                                                                |
| ----------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Synchronous generation  | Why no queue at this scale (ADR-1)                     | "Your function times out at 75 s and the model sometimes takes 70. What happens to the paid call? The user's retry?" · "When would you switch to a queue, and what changes in the API?" |
| Cost control            | Four layers, why each exists                           | "Two Vercel instances: what is your real per-visitor limit?" · "Why reserve budget before the call? What if the call fails?" · "Show me how the overshoot happens step by step."        |
| Deadline bug            | urllib timeout semantics, slow drip, thread + deadline | "You leave a thread running after the timeout. How many can pile up? What does it hold?" · "Why not `httpx`?" · "Is the abandoned call still billed?"                                   |
| Duplicate single-flight | `lead`/`done`, waiter cap                              | "What if the leader crashes?" · "Can an attacker park threads with duplicates?" · "Why does it not work across instances, and does that matter?"                                        |
| Validation              | draft decode, alternatives table                       | "Why not let the model reject bad images?" · "What about HEIC, which most iPhones produce?" · "Decompression bombs?"                                                                    |
| Measurement method      | client calibration, warm-up, reps, baselines           | "Your load generator shares 4 vCPUs with the server. How do you know?" · "Why are your p99s noisy?" · "What is Little's law telling you here?"                                          |
| Ownership               | what you specified, decided, reviewed                  | "Which part did you write yourself?" · "Walk me through `run_generation` without looking." · "What did the AI get wrong, and how did you catch it?"                                     |
| Not done                | real model, Blob, staging                              | "You never called the real API. Why should I believe any of it works?"                                                                                                                  |

## 4. Weaknesses

**Overclaims to remove or avoid**

- PR #2's gap audit lists upload security and cost controls as PASS; measured, both had holes (now fixed). Do not reuse those reports as evidence without the corrections in [05](05-engineering-improvements.md).
- "60 s deadline", "never pays twice", "bounded overshoot": all were stated in code comments and were not true before this branch.
- Any phrasing that implies the AI integration is proven. It is integrated against documentation only.

**Engineering gaps**

- No real model call, no real storage, no deployment verification, no users.
- No observability beyond log lines; no metrics or alerts; no runbook.
- Limits are per instance; budget is approximate across instances.
- Container image runs as root without a healthcheck; the web container is a dev server.
- Benchmarks are from one shared sandbox; no CI benchmark to catch regressions.

**Not yet impressive**

- Read-path performance (normal FastAPI numbers).
- Docker and CI (competent, standard).
- Scale: ≈1 k lines of backend, 3 seed recipes, 2 concurrent calls.

## 5. Final verdict

**Not yet competitive as a stand-alone international case study for ML / ML-infra roles; a reasonable supporting project for AI-application, AI-platform and solutions roles, once three pieces of evidence exist.**

What is missing, precisely:

1. **One real end-to-end run.** A staging deploy with Blob connected, one verified recipe, and a small, budgeted batch of real Gemini calls (e.g. 20 calls ≈ $0.72): record real latency p50/p95, failure rate, cost per successful image, and one example of each fallback. Without this, the core claim is untested.
2. **Personal, demonstrable ownership.** Pick one component (for example the single-flight or the deadline) and be able to rebuild it from scratch on a whiteboard, or write a follow-up yourself (e.g. structured logging with request IDs, or a queue-based variant behind a flag) with your own commits.
3. **Operational evidence.** Basic structured logs or metrics from the staging run (requests, fallbacks by reason, spend per day) and a one-page runbook.

For ML/ML-infra applications, pair MOSAIC with a project that shows your actual specialty (model conversion and deployment: e.g. ONNX/TensorRT conversion of a model, with accuracy-parity tests and latency/throughput on real hardware). That would be differentiated in a way MOSAIC cannot be.
