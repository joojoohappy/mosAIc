# 10 · Engineering learning report

How this evaluation was actually done, step by step, with what each step produced. Written for an engineer with a few years of experience who wants the method, not just the conclusions. Every step here has an artefact in the repository or in [the execution log](execution-log.md).

## 1. How the audit started

**Order of reading.** Not the README first. The sequence was:

1. `git log` and the PR #2 description: what changed recently and what the authors _claim_ (the claims become the test plan).
2. The backend entry point, [`main.py`](../../apps/backend/app/main.py), top to bottom, because one HTTP route (`POST /api/generate`) is where money is spent. Every `if` in that function is a decision.
3. The modules it calls in the order it calls them: `validate_upload` → `limits` → `run_generation` → `provider.generate` → `storage`.
4. Only then tests, CI and docs, reading them as _claims to check_ rather than as facts.

**What to look for while reading.** Three kinds of sentence in comments and docs are worth writing down, because they are testable:

- Guarantees: "a double click or a refresh mid-generation never pays twice"; "60 s deadline"; "a real decode so a renamed or truncated file is caught".
- Bounds: "can overshoot by at most `MOSAIC_MAX_CONCURRENT` per instance".
- Invariants: "only `_write_result` touches storage".

Each became a scenario in [`bench_reliability.py`](../../benchmarks/bench_reliability.py). Four of them turned out false.

**Run the existing suite before changing anything.** It passed 6/7 here, and the failure was environmental (Node 22 vs required ≥ 24). Fixing the environment, not the test, gave a clean baseline. Lesson: when a check fails on first run, first ask "is my environment the one this repo expects?"

## 2. How the important issues were found

| Issue                             | How it surfaced                                                                                                         | The observation that mattered                                                                                                                          |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| JPEG validation did nothing       | [`bench_stages.py`](../../benchmarks/bench_stages.py) timed `validate_upload` at **0.03 ms for 0.3, 3 and 12 MP alike** | Work that does not scale with input size is not doing the work you think. A decode of 12 MP cannot take 30 µs.                                         |
| Timeout was per read              | Reading `urlopen(timeout=...)` and knowing its semantics; then a slow-drip mode in the fake server                      | Docstring in `generation.py` mentioned "a zombie thread that finishes after the timeout", but no thread existed: documentation from an earlier design. |
| Overlapping duplicates paid twice | The dedupe cache is written _after_ generation; so the window is the whole model call                                   | The E2E test that claims to cover it waits 3.5 s for a 3 s model before retrying. A test can pass without testing its title.                           |
| Temp-file collision               | A benchmark crashed: `JSONDecodeError` parsing a plain-text 500                                                         | The crash of your own tool is data. The server log had `FileNotFoundError` on `usage-<day>.json.tmp`.                                                  |

Pattern: three of four came from **a number that did not fit a mental model** or **a tool failure**, not from code review. Code review found the fourth only because the timeout semantics were already known.

## 3. How testing was prioritised

Ranked by _cost of being wrong × likelihood × cheapness to test_:

1. Paths that spend money (generate, budget, duplicates, validation before the call): highest cost per defect.
2. Failure handling of the external dependency: certain to happen in production, easy to simulate with a fake server.
3. Abuse controls: cheap to test, embarrassing if broken.
4. Read-path performance: cheap, but low stakes at this traffic. Done mainly as a baseline and for regression checking.
5. Deployment: start/restart only, because the real target (Vercel) is not reachable from here.

Things deliberately _not_ tested: real model behaviour (no key, no budget approval), Vercel cold starts, visual output quality. Writing these down is as important as the tests that ran.

## 4. Why these benchmarks and not others

- **No GPU / inference metrics:** there is no model in the process. Reporting them would be fabrication.
- **No "generation throughput":** throughput is fixed by design at `MAX_CONCURRENT / model_latency`. The meaningful question is what happens _past_ the cap, hence the shedding benchmark.
- **Generation latency measured as MOSAIC's overhead only,** with the model set to 0 s, so the number isolates the code you control.
- **Memory per in-flight generation,** because the request holds the photo several times over (bytes, base64, JSON) and serverless functions have fixed memory. It turned out to be ~30–44 MB per 7.6 MB upload, which explains why the concurrency gate is also a memory guard.
- **Reliability scenarios as the main suite,** because the architecture's value claims are reliability claims.

**Calibrate the load generator.** The first read-latency run used a Python `httpx` async client. It showed p50 ~100 ms at concurrency 32 while the server used ~15 % of a core. Low server CPU + high latency means the bottleneck is not the server. Re-running with k6 gave ~12 ms ([`client_calibration.json`](../../benchmarks/results/client_calibration.json)). Always check: _is my client faster than the thing I am measuring?_

**Baselines from a separate checkout.** The baseline was produced by running the same harness against a `git worktree` of the original commit (`MOSAIC_BENCH_SRC`). This avoids "I measured before, changed the harness, then measured after", which silently compares different experiments.

## 5. How results were interpreted

- **Saturation, using Little's law.** Concurrency = throughput × latency. At 32 clients and ~945 req/s, expected latency is ~34 ms; measured p50 was 31 ms. When the law holds, the system is simply full; latency rises because requests wait, not because something broke.
- **CPU per request.** `/api/recipes` saturated at ~0.9–1.0 core and ~900 req/s → ~1 ms CPU per request; `/api/health` at ~0.6 core and ~2,600 req/s → ~0.2 ms. The 0.8 ms difference is the work of reading and serialising recipes. Knowing the cost per request lets you answer capacity questions without more benchmarks.
- **Variance.** Every cell has 3 repetitions; tables show median and range. p99 ranges are wide (e.g. 46–82 ms), so p99 differences under ~30 % between runs are noise on a shared machine. Before/after read latencies were declared "no change" for this reason.
- **Counts beat timings for correctness.** Provider calls per scenario, HTTP 500s per trial, damaged files that reached the provider. These are exact and do not need statistics.
- **Report regressions.** Generate overhead got slower (+13.7 ms at 3 MP). That is in the headline table, not hidden.

## 6. How trade-offs were evaluated

The validation fix is the clearest example. Four options were measured on the same corpus for both cost and detection ([`compare_validation.py`](../../benchmarks/compare_validation.py)). The cheapest correct-looking option (check for the JPEG end marker) had a hidden false positive: valid photos with data after the marker. That only appeared because the corpus included a "valid + trailing bytes" case. **Always include valid inputs that look unusual in a validation corpus**, not only broken ones.

Criteria used for every fix: does it change money or correctness for a user; is it measurable; how many lines; does it add a dependency or a service; can it be wrong in a new way (e.g. single-flight waiters holding threads → capped at 8 and still rate-limited).

## 7. Assumptions that proved incorrect

| Assumption (before measuring)                               | Reality                                                                                                                                              |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| The release reports' PASS marks are reliable                | Two PASS areas had defects                                                                                                                           |
| `verify()` decodes images                                   | Only for PNG CRCs; JPEG headers only                                                                                                                 |
| A 60 s timeout bounds the call                              | Bounds each socket read                                                                                                                              |
| Budget overshoot is bounded by concurrency                  | Lost updates are cumulative; 73 vs 50 observed                                                                                                       |
| The Python load client is fast enough for a local benchmark | ~9× higher latency than k6 on the same server                                                                                                        |
| `docker build` will just work                               | The sandbox's TLS proxy needed its CA inside the build; later Docker Hub rate-limited base-image lookups, so build times could only be measured once |
| A chunked oversized body returns 413                        | It returned FastAPI's 400 (still refused); fixed in a follow-up                                                                                      |

## 8. Improvements that were not worth implementing

See the table at the end of [05](05-engineering-improvements.md). The reasoning pattern: an optimisation is worth doing when its gain is visible to a user or a bill at _this_ system's scale. Caching `recipes.json` saves 0.05 ms of a 1 ms request on an endpoint that already does ~900 req/s per worker. A cross-process atomic counter protects against a few extra $0.036 calls and cannot be built on the deployed storage without new infrastructure. Recording _why not_ is part of the engineering, and it is what lets someone revisit the decision when scale changes.

## 9. How resume-worthiness was judged

A claim is resume-worthy when it passes all three:

1. **Measured, with a file behind the number.** "6/6 → 1/6 damaged uploads reached the paid API" qualifies. "Improved reliability" does not.
2. **Ownership you can defend.** Git history shows who wrote what; the bullets in [09](09-hiring-review.md) are worded around specifying, directing, measuring and deciding, because that is the defensible part.
3. **Relevant to the target role.** Cost and failure control around a paid model API is relevant to AI-application and platform roles; it is not evidence of ML or ML-infrastructure skills, so it is not presented as such.

Things that failed the test: read-path throughput (ordinary), Docker (standard), anything about Gemini performance (never measured).

## 10. If you repeat this on another project

1. List every testable claim in docs and comments before running anything.
2. Get the existing suite green in the environment the repo expects.
3. Build a fake for each external dependency that can misbehave on command.
4. Calibrate your load client; record environment details with every result.
5. Run baselines from a separate checkout of the original commit.
6. Prefer counts over timings for correctness; repeat timings and report ranges.
7. For each fix: regression test that fails before and passes after, re-run the same benchmark, report regressions too.
8. Write down what you chose not to do and why.
