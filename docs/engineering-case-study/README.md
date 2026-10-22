# MOSAIC engineering case study

An evidence-based evaluation of MOSAIC's v0.1 release candidate (PR #2, `fbbc625`): what it implements, how it behaves under measurement, four defects found and fixed, and an honest assessment of its production readiness and portfolio value.

**Read first:** [08 · Portfolio case study](08-portfolio-case-study.md) (summary for readers) and [09 · Hiring review](09-hiring-review.md) (skeptical assessment).

> Every figure involving image generation was measured against a **local fake model server**. No real Gemini call was made and nothing was deployed. See [03](03-benchmark-methodology.md) §5 for what the numbers do and do not show.

## Documents

| #   | Document                                                           | What it answers                                                                              |
| --- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| 01  | [Architecture audit](01-architecture-audit.md)                     | What is implemented, verified, partial, planned; architecture diagram with source references |
| 02  | [Engineering value assessment](02-engineering-value-assessment.md) | Which capabilities are strong evidence (A) through unsupported (D)                           |
| 03  | [Benchmark methodology](03-benchmark-methodology.md)               | What is worth measuring here, workloads, sample sizes, environment, threats to validity      |
| 04  | [Benchmark results](04-benchmark-results.md)                       | All measurements, baseline vs. after                                                         |
| 05  | [Engineering improvements](05-engineering-improvements.md)         | The four fixes, alternatives, before/after, what was not done                                |
| 06  | [Production readiness](06-production-readiness.md)                 | Classification: **Validated Prototype**                                                      |
| 07  | [Architecture decisions](07-architecture-decisions.md)             | 10 ADRs and what changes at scale                                                            |
| 08  | [Portfolio case study](08-portfolio-case-study.md)                 | The English case study                                                                       |
| 09  | [Hiring review](09-hiring-review.md)                               | Role scores, resume bullets, interview questions, weaknesses, verdict                        |
| 10  | [Engineering learning report](10-engineering-learning-report.md)   | How the evaluation was done and why                                                          |
| –   | [Execution log](execution-log.md)                                  | What was run, in order, with evidence; what was not done                                     |

## Charts

|                                            |                                                       |
| ------------------------------------------ | ----------------------------------------------------- |
| [B1 read latency](img/b1-read-latency.png) | [B2 generate overhead](img/b2-generate-overhead.png)  |
| [B2 memory](img/b2-memory.png)             | [B3 reliability before/after](img/b3-reliability.png) |

## Benchmarks and raw data

Scripts: [`benchmarks/`](../../benchmarks/) ([how to run](../../benchmarks/README.md)). Results: [`benchmarks/results/`](../../benchmarks/results/).

| Benchmark                              | Script                                                                                       | Raw results                                                    |
| -------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| B1 read endpoints (k6)                 | [`bench_api.py`](../../benchmarks/bench_api.py), [`k6/read.js`](../../benchmarks/k6/read.js) | `api_latency_{baseline,after}.json`, `*_raw.csv` (per request) |
| B2 generate overhead, shedding, memory | [`bench_generate.py`](../../benchmarks/bench_generate.py)                                    | `generate_{baseline,after}.json`                               |
| B2b stage timing                       | [`bench_stages.py`](../../benchmarks/bench_stages.py)                                        | `stages_{baseline,after}.json`                                 |
| B3 reliability scenarios               | [`bench_reliability.py`](../../benchmarks/bench_reliability.py)                              | `reliability_{baseline,after}.json`                            |
| Validation alternatives                | [`compare_validation.py`](../../benchmarks/compare_validation.py)                            | `validation_alternatives.json`                                 |
| Load-client calibration                | [`calibrate_client.py`](../../benchmarks/calibrate_client.py)                                | `client_calibration.json`                                      |
| B4 container                           | [`bench_deploy.sh`](../../benchmarks/bench_deploy.sh)                                        | `deploy.json`                                                  |
| Regression tests on both checkouts     | [`tests/test_hardening.py`](../../apps/backend/tests/test_hardening.py)                      | `regression_tests_on_{baseline,branch}.log`                    |
| Full suite                             | [`scripts/test-all.sh`](../../scripts/test-all.sh)                                           | `test-all-after.log`, `test-all-final.log`                     |
| Tables used in 04                      | [`report_tables.py`](../../benchmarks/report_tables.py)                                      | `tables.md`                                                    |

## Code changes in this branch

- [`apps/backend/app/generation.py`](../../apps/backend/app/generation.py): JPEG/WebP uploads are decoded, not just header-checked.
- [`apps/backend/app/provider.py`](../../apps/backend/app/provider.py): wall-clock deadline for the model call.
- [`apps/backend/app/limits.py`](../../apps/backend/app/limits.py), [`main.py`](../../apps/backend/app/main.py): overlapping identical requests share one generation; corrected budget docstring.
- [`apps/backend/app/storage.py`](../../apps/backend/app/storage.py): unique temp names for atomic local writes; Blob read errors logged via `logging`.
- [`apps/backend/tests/test_hardening.py`](../../apps/backend/tests/test_hardening.py): 11 regression tests.
