# mosAIc — Engineering Case Study

An evidence-based audit, benchmark and reliability-hardening pass over `joojoohappy/mosAIc` at `c76a78a`, carried out 2026-10-23.

**Bottom line**: a well-reasoned *serving shell* for an AI image service (provenance-first result pipeline, solid trust boundaries, failure-aware client) whose AI provider is not implemented yet. Classified as a **Validated Prototype**. Three reliability defects that would surface as soon as a real model is attached were measured and fixed.

**Start here → [CASE-STUDY.md](CASE-STUDY.md)** (one page, for reviewers). The documents below are the supporting evidence.

## Documents

| # | Document | What it answers |
|---|---|---|
| 01 | [Architecture audit](01-architecture-audit.md) | What is actually implemented, with file references and a status per component |
| 02 | [Engineering value assessment](02-engineering-value-assessment.md) | Which parts are portfolio-grade (A–D) and for which roles |
| 03 | [Benchmark methodology](03-benchmark-methodology.md) | What can/cannot be measured here, scenarios, environment, reproduction |
| 04 | [Benchmark results](04-benchmark-results.md) | Baseline vs after, every number traceable to `benchmarks/results/` |
| 05 | [Engineering improvements](05-engineering-improvements.md) | Problem → alternatives → change → regression → re-measurement |
| 06 | [Production readiness](06-production-readiness.md) | Classification and the evidence for it |
| 07 | [Architecture decisions](07-architecture-decisions.md) | ADRs: original decisions, this study's decisions, and rejected ones |
| 08 | [Portfolio case study](08-portfolio-case-study.md) | The English write-up for reviewers |
| 09 | [Hiring review](09-hiring-review.md) | Role scores, resume bullets, interview questions, verdict |
| 10 | [Engineering learning report](10-engineering-learning-report.md) | How the audit was done and what went wrong along the way |
| — | [Execution log](execution-log.md) | Chronological record of every activity and its evidence |

## Code and data

| Path | Content |
|---|---|
| [`benchmarks/`](../../benchmarks/) | Harness, load generator, scenarios, fixtures, [raw samples](../../benchmarks/raw/), [results JSON](../../benchmarks/results/), [summary tables](../../benchmarks/results/summary.md), [charts](../../benchmarks/charts/) |
| `apps/backend/app/main.py`, `generation.py` | ADR-7 (generation limiter, async health), ADR-8 (provider deadline), ADR-9 (upload guard) |
| `apps/backend/tests/test_generation.py` | +3 tests (`ProviderDeadline`) |
| `apps/backend/tests/test_api.sh` | bounded start-up wait; +3 oversize checks that assert the error body |
| `apps/backend/.env.example` | documents `MOSAIC_PROVIDER_TIMEOUT_S`, `MOSAIC_MAX_CONCURRENT_GENERATIONS` |
| `.github/workflows/ci.yml` | CI for all existing checks — **not yet executed** |

## What was not done (and why)

- No model/provider benchmarks: there is no model in the repository.
- No frontend build, typecheck or E2E: the package registry was unreachable from both available environments.
- No Docker run: no Docker daemon available.
- No push, deploy or paid API call.
