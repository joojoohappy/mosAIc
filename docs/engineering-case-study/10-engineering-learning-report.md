# 10 — Engineering Learning Report

How this audit was actually done, step by step, with what worked and what did not. Written for an engineer with ~2.5 years of experience. Every step below has an artefact in the repo or in [execution-log.md](execution-log.md).

---

## 1. Start by finding the code, not by reading the brief

The brief described an "AI system" and listed things to benchmark (GPU, tokens, model latency). The first hour went to locating the repository:

- `~/mosAIc` on the laptop: **only empty folders**.
- `~/ai-creative-playground-main/mosaic`: a Build Day prototype whose `app/api/generate/route.ts` was `export {}` and whose "generation" was a canvas drawing.
- The GitHub repo (`joojoohappy/mosAIc`, 16 commits): the real thing — FastAPI backend, typed client, Next.js frontend.

**Lesson**: the first deliverable of an audit is "what is the system?" — and the answer can invalidate half of the requested work. Here it removed every model-performance benchmark from scope, because `_call_provider()` raises `NotImplementedError`. Reporting "N/A, here is why" is a result; inventing a model benchmark would have been the single most damaging thing to put in a portfolio.

## 2. How the audit was structured

1. **Inventory** (`git ls-files`, line counts) → which files carry logic? Of ~3,700 tracked lines, the backend logic is ~330 lines and the client ~200. That tells you where to spend reading time.
2. **Read the docstrings and commit messages as claims.** This repo is unusually explicit: `main.py` says "/api/health stays responsive while a generation is in flight"; `generate()` says "there is no reason to pull 8MB off the wire"; `_call_provider` says "Must honour: a hard deadline". Each sentence is a testable hypothesis.
3. **Run the existing tests before writing new ones.** 36 + 17 + 9 + 5 passed. This establishes that the environment is faithful *and* tells you what is already covered, so new tests go where coverage is missing.
4. **Turn the claims that matter for the next milestone into experiments.** The next milestone is "plug in a slow, sometimes-hanging, paid provider". So: concurrency (S2), hangs (S4), abuse of the upload path (S3), storage growth (S5).

## 3. How the important issues were identified

| Claim in code | Experiment | Result |
|---|---|---|
| "health stays responsive while a generation is in flight" | S2: N slow generations, then one health probe | True up to 39; at 40 the probe waited ~4.8 s. 40 = AnyIO's default thread-pool size. The claim was verified by the authors with **one** 8 s generation — correct, but one is not many. |
| "checked before the upload is read … no reason to pull 8MB off the wire" | S3: 9–256 MB uploads to a not-ready recipe | The client sent all 268 MB and the server parsed it before answering 403. FastAPI parses the multipart body *before* the route function runs, so "before the upload is read" is impossible inside the route. |
| "Must honour: a hard deadline" | S4: provider that never returns | Nothing enforced it; the request stayed open until the client gave up. |

Pattern worth remembering: **frameworks do work before your code runs** (body parsing, dependency resolution, thread-pool scheduling). Comments describe what the author's code does; benchmarks reveal what the framework does around it.

## 4. Why these benchmarks and not others

- A latency table for every endpoint (S1) is the benchmark everyone expects, and it was run — but it is the **least informative** one here: on loopback with no provider, it measures JSON serialisation and file I/O (p50 ≈ 1.1–1.9 ms). It is useful as a regression guard for the changes, not as a headline.
- The informative benchmarks were the ones designed to **falsify a specific claim** (S2–S4). Each has a binary outcome you can explain in one sentence in an interview.
- S2 needed care to be trustworthy: the first version probed health 1 s after launching N requests and got noisy results (sometimes 1.5 ms, sometimes 2.5 s), because the requests had not all reached the pool yet. The final version waits until the server's thread count stabilises, uses a 1×1 upload to isolate the thread-pool effect, repeats on a fresh server 3 times, and also runs the realistic 1.6 MB upload. The cliff at exactly 40 is reproducible to within ~2 %.

## 5. How the results were interpreted

- **Look for the mechanism, not just the number.** "Health got slow" is a symptom; "the 41st task waits for a free thread in a 40-slot `CapacityLimiter`" is a mechanism, and it predicts the result (wait ≈ remaining provider time ≈ 4.8 s of a 5 s sleep). When the prediction matches, you understand the system.
- **Check that a fix moves the right metric and note what it costs.** The generation limiter makes health immune to load (see [04](04-benchmark-results.md)), but generation throughput becomes `limiter / provider_latency`. With 8 slots and 5 s, 60 requests take ~40 s — that is a deliberate trade, and it is why the limit is an environment variable tied to the provider's rate limit, not a constant.
- **Separate the environment from the system.** The load generator and server shared 2 vCPUs. Absolute rps numbers are a property of the sandbox; only before/after comparisons on the same box are claimed.

## 6. Architectural trade-offs, evaluated

- *Shared pool vs dedicated limiter vs job queue* (ADR-7, ADR-3): the queue is the "right" long-term answer, but it changes the public API and the frontend; the limiter fixes the measured problem in ~5 lines without changing any contract. Choose the smallest change that removes the measured risk; record the bigger change as a scale trigger.
- *Abandoning a thread on timeout* (ADR-8) is normally dangerous. It is safe here only because of an existing invariant — the provider function never writes; one write happens after the mode is decided. Good earlier design made a later fix cheap. A new test pins that invariant under the deadline.
- *Early 400 on oversized bodies* (ADR-9) changes behaviour in two visible ways (precedence over 403; some clients see a reset). Both are written down rather than hidden.

## 7. Assumptions that turned out wrong

1. "The local folder `~/mosAIc` is the repo." — It was an empty skeleton.
2. "I can build and benchmark the Next.js frontend." — Both the sandbox and the linked laptop VM had package registries blocked; even FastAPI had to be installed from its GitHub source (pure Python). The frontend stays "implemented, unverified" rather than being guessed at.
3. "The backend tests will just run." — `test_api.sh` hung forever: the venv had no `uvicorn` entry point and the script's wait loop has no bound. That became finding F7.
4. "The early 400 will look the same to every client." — Chromium and curl read it; Node's undici and Python's urllib reported a connection reset. Measured, then documented as a trade-off.
5. **My own harness had a bug**: S1 stalled for minutes because the benchmark launched the server with `stdout=PIPE` and never read it. The backend `print()`s one line per fallback; after ~64 KB the pipe filled and the server blocked inside `print`. Fix: log to a file. Lesson: a benchmark harness is code and deserves the same suspicion as the system under test — if a result looks like a hang, first check whether *you* caused it.
6. The first fix for chunked oversized uploads raised an exception inside `receive()`. FastAPI caught it during form parsing and turned it into a generic `400 {"detail": "There was an error parsing the body"}` — right status, wrong error code, so the frontend would show "request failed" instead of "photo must be under 8 MB". Caught because the smoke test was extended to assert the **body**, not just the status.

## 8. Improvements that were not worth implementing

| Idea | Why not (with numbers) |
|---|---|
| Cache `recipes.json` | 31 µs per read vs ≥1.5 ms per request; re-reading lets the team flip `tryReady` without a restart. |
| Reference the fallback image instead of copying it per result | Saves 1.5 MB/request but breaks result immutability (old results would point to a regenerated image whose provenance note no longer matches). Retention is the right fix. |
| Pin dependencies | Correct, but I could not install the versions the authors used; pinning the sandbox's source-built FastAPI would claim a tested configuration that nobody tested. Left as a recommendation. |
| Job queue | Contract change with no traffic to justify it. |
| Client-side image downscaling | Probably valuable once a provider exists (F10), but the frontend could not be built or tested here — an untested frontend change is a liability. |

## 9. How "resume-worthy" was decided

A bullet survives only if all three hold:
1. **The action is yours** (check `git log`; here the backend and frontend were written by a teammate and a coding agent — see [09](09-hiring-review.md)).
2. **The mechanism is explainable** in two sentences to a sceptical interviewer.
3. **The number is reproducible** from a script in `benchmarks/` and does not depend on a component that does not exist.

That rule removed: anything about "AI generation performance", "production", "users", and the S1 throughput table as a headline. It kept: the thread-pool cliff and its fix, the deadline, the upload guard, and the provenance design (with honest authorship).

## 10. What to practise next

- Read framework source when a claim depends on it (Starlette's `run_in_threadpool`, AnyIO's default limiter, FastAPI's form parsing).
- Write the experiment *before* the fix, keep the baseline tree (`git archive`), and run before/after with the same harness.
- Assert error **codes and bodies** in tests, not only HTTP statuses.
- Treat "N/A — component does not exist" as a legitimate, valuable benchmark result.
