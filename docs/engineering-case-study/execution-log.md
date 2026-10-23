# Execution Log

Chronological record of what was actually done, 2026-10-23 (Asia/Taipei). "Evidence" points to an artefact that can be re-run or inspected.

| # | Activity | Outcome | Evidence |
|---|---|---|---|
| 1 | Located the project on the user's laptop | `~/mosAIc` = empty folder skeleton; `~/ai-creative-playground-main/mosaic` = 2026-09-20 Build Day prototype (mock canvas "generation", empty API route); `.../main` = Build Day planning docs | §8 of [01](01-architecture-audit.md) |
| 2 | Tried to install the prototype's deps in the sandbox and in the laptop's Linux VM | npm registry blocked in both (DNS failure / proxy 403) | — |
| 3 | User pointed to GitHub `joojoohappy/mosAIc`; cloned `main` @ `c76a78a` | 16 commits; FastAPI + Next.js monorepo | `git log` |
| 4 | Read all tracked source, docs, commit messages | Findings F1–F11 | [01](01-architecture-audit.md) |
| 5 | Installed backend runtime | PyPI blocked; FastAPI 0.160.0 and `annotated-doc` installed **from their GitHub source** (pure Python); Starlette 1.7.0, uvicorn 0.54.0 pre-installed | `.venv` with `.pth` to vendored source (not committed) |
| 6 | Ran existing backend unit tests (baseline) | **36/36 pass** | `python -m unittest discover -s tests` |
| 7 | Ran `tests/api.test.mjs` (Node 22, `--experimental-strip-types`) | **9/9 pass** | — |
| 8 | Ran `tests/image-upload-wire.test.mjs` (real uvicorn) | **5/5 pass** | — |
| 9 | Ran `apps/backend/tests/test_api.sh` | First attempt **hung** (unbounded wait; no `uvicorn` script in venv) → F7. With a `uvicorn` shim: **17/17 pass** | — |
| 10 | Tried to run `pnpm typecheck`/`build` for `apps/web` | **Not executed** — npm registry unreachable. Frontend left "implemented, unverified" | — |
| 11 | Tried Docker | **Not executed** — no Docker daemon | — |
| 12 | Wrote benchmark harness (`run_backend.py`, `loadgen.mjs`, `run_scenarios.py`) and seeded fixture | — | [`benchmarks/`](../../benchmarks/) |
| 13 | Baseline S3, S5, S6, S7, S2 (first version), S4 | S2 v1 noisy → redesigned (thread-count wait, 3 trials, two upload sizes) | `benchmarks/results/baseline.json` |
| 14 | Baseline S1 first attempt | **Stalled** — harness bug: server stdout piped and never read; 64 KB pipe filled. Fixed (log to file) and re-ran | [10 §7](10-engineering-learning-report.md) |
| 15 | Implemented ADR-7 (generation limiter, async health), ADR-8 (provider deadline), ADR-9 (upload guard), F7 fix (bounded wait), 3 new unit tests | 39/39 unit, 17/17 smoke, 9/9, 5/5 | `git diff c76a78a -- apps/backend` |
| 16 | Probed early-400 behaviour per client | curl (with/without `Expect`) and Chromium read the 400; Node undici and Python urllib saw a reset | ADR-9 |
| 17 | Found chunked-upload path returned FastAPI's generic 400 (`detail`) instead of `too_large` | Reworked middleware (answer + synthetic disconnect); added 3 smoke checks that assert the body; 20/20 | `test_api.sh` |
| 18 | Collapsed `MOSAIC_PROVIDER_WORKERS` into the single generation limit (pool = 2 × limit) after S2 with limit 40 showed the provider pool silently capping at 8 | Regression re-run: all pass | `generation.py` |
| 19 | Re-ran all "after" scenarios on the final code; re-ran baseline S1 with `--src` = `git archive c76a78a` for a same-session comparison | — | `benchmarks/results/{baseline,after,after-limit40}.json` |
| 20 | Generated tables and charts | — | `benchmarks/results/summary.md`, `benchmarks/charts/` |
| 21 | Added `.github/workflows/ci.yml` | Executed later, see #25 | file |
| 22 | Wrote documents 01–10, README | — | this folder |
| 23 | Cross-checked every number in 04/05/08/09 against `summary.md` | see bottom of [04](04-benchmark-results.md) | — |
| 24 | External review (ChatGPT) of the ZIP | Corrected: S3 metric is curl `size_upload` = bytes the **client sent** (was mislabelled "received" in the chart, 05, 08, 09); provider deadline reworded as bounded response time with fallback (the call is not cancelled); magic-byte check described as a header check, sidecars as consistency checks. Added one-page `CASE-STUDY.md` | follow-up commit |
| 25 | Pushed branch, opened [PR #4](https://github.com/joojoohappy/mosAIc/pull/4); first CI run | **All steps green** in GitHub Actions: backend unit tests, HTTP smoke test, `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm test`, `pnpm build` | [run](https://github.com/joojoohappy/mosAIc/actions/runs/39916292304) |

## Final regression status (final code)

| Suite | Result |
|---|---|
| Backend unit tests | 39/39 (36 original + 3 new) |
| HTTP smoke test | 20/20 (17 original + 3 new) |
| Client unit tests | 9/9 |
| Real-HTTP wire tests | 5/5 |
| Web typecheck / build | not run locally; **pass in CI** |
| CI | [green](https://github.com/joojoohappy/mosAIc/actions/runs/39916292304) |
