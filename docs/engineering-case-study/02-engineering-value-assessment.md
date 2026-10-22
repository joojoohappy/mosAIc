# 02 — Engineering Value Assessment

Perspective: a senior interviewer reading the repo cold, for AI/ML Engineer, ML Platform/Infra, Software Engineer and Solutions roles.
Only capabilities that exist in the code are assessed. Categories: **A** strong evidence · **B** valuable but needs validation · **C** ordinary · **D** unsupported claim.

## Ownership first

`git log` shows three authors: `joojoohappy` (repo owner: Build Day plan, scaffold, PR merge — 5 commits), **Zoe Wu** (FastAPI backend, tests, monorepo restructure, Docker — 10 commits, co-authored with Claude), and a **Codex** agent (the Next.js frontend and workspace migration — 1 commit, merged by joojoohappy). The Build Day plan assigns "Person 2 — Backend / AI / Systems" to the teammate.
**Every highlight below must be presented with honest attribution.** If the backend is not your code, the defensible claims are product ownership, contract design, review/integration of AI-agent output, and — after this study — the measured reliability fixes. If you *are* the backend author under another identity, say so explicitly in interviews; the commit history will be read.

## Highlights

### H1. Server-authored provenance for AI output (live / cached / mock) — **A**

- **Problem**: an AI demo that silently shows a pre-made image as "your result" is misleading; the project's product principle forbids it.
- **Why meaningful**: provenance is decided in one place (`run_generation`), written by the server (`_source_note`), validated by content (sidecar must parse, have 5 provenance fields, point inside `fallback/`, and *be an image*), and the client refuses inconsistent payloads (`isGenerationResult`: `mock` must have `imageUrl === null`).
- **Alternatives**: client-side labels; a single boolean `isLive`; trusting sidecar existence.
- **Trade-offs**: more fields on the wire; every fallback asset needs a sidecar; copying the asset per result costs disk (S5) but keeps old results truthful if the asset changes.
- **Measurement**: 20 unit tests across `Modes` (6), `Disclosure` (4), `SidecarValidation` (10); 1 client test. Re-run: all pass.
- **Roles**: AI Engineer, Solutions Architect (responsible-AI UX), Software Engineer.

### H2. Prompt confidentiality and trust boundaries — **A**

- `recipeId`-in / prompt-out; allowlist projection; magic-byte sniffing at the upload *and* provider-output boundary; 32-hex result id validated before any path join; path-escape check for sidecar images.
- Evidence: unit tests `PublicProjection` (4), `ImageSniffing` (2), `ResultStore.test_rejects_ids_that_are_not_32_hex`, `SidecarValidation.test_image_path_cannot_escape_fallback_dir`; smoke checks "list omits prompt", "path traversal".
- **Roles**: AI Platform, Security-minded SWE, Solutions.

### H3. Failure-aware typed API client — **A−**

- Per-call timeouts (10 s, 75 s for generate), health probe to classify failures (`backend_unavailable` vs `request_timeout` vs `request_failed`), no retry for the non-idempotent generate, runtime guards on every payload.
- Evidence: 9 unit tests + 5 real-HTTP wire tests (real undici multipart into real FastAPI).
- Weakness found by this study: the health-probe classification is only as good as health's own availability — under thread-pool saturation the probe itself waited ~4.8 s (S2), so a busy server could be reported as down. Fixed in [05](05-engineering-improvements.md).
- **Roles**: SWE, Platform.

### H4. Concurrency model for a slow external model call — **B → A after this study**

- Original: sync routes in Starlette's thread pool. Correct for one request; **measured cliff at 40 in-flight generations** (health 2–3 ms → ~4.8 s).
- After this study: a dedicated capacity limiter for generation, `async` health, a hard provider deadline, and request-size enforcement before body parsing, each with before/after numbers.
- **Roles**: ML Infrastructure, AI Platform — this is the most relevant item for infra roles because it is exactly the problem of serving a slow, rate-limited model behind an API.

### H5. Testing discipline — **B+**

- 36 unit tests with filesystem isolation, a 17-check HTTP contract test, a real-wire integration test that spins up an isolated backend copy. Tests encode *product invariants* ("fallback never claims the user's photo"), not just functions.
- Gaps: no CI (so nothing enforces them), no frontend component/E2E tests, smoke test mutates real data (F8).

### H6. Monorepo with shared contracts (`packages/types`, `api`, `core`) — **C+**

- Sensible structure; the same client is intended for a future Expo app. Ordinary for a modern TS repo; value depends on a second consumer that does not exist yet.

### H7. Docker / compose — **C**

- Self-described "verification-only"; web container runs `next dev`; compose requires a local `.env`. Not a deployment.

### H8. Web UI (Figma-based screens, favorites, drag-and-drop upload) — **C**

- Competent product UI produced by a coding agent. Not verified in this study (Next.js unavailable).

## Claims to avoid (category D)

| Claim | Why unsupported |
|---|---|
| "Built an AI image-generation pipeline" | No model is ever called. The pipeline *around* a model is built. |
| Any model latency, cost, throughput or quality number | None exists. |
| "Production-deployed" / users / uptime | Nothing is deployed. |
| "Health stays responsive while generation runs" (as an unconditional property) | False at ≥40 concurrent generations on the original code (S2). |
| "Unverified recipes are rejected before the upload is read" | The whole body is received first (S3, S1). |

## Summary by role

| Role | Most relevant evidence | Biggest gap |
|---|---|---|
| AI Engineer | H1, H2 | no model integration, no eval |
| ML Engineer | — | no training, no inference, no data |
| ML Infra / AI Platform | H4 (+ this study's measurements), H3 | no real provider, no deployment, no observability |
| Software Engineer | H2, H3, H5, H4 | frontend unverified, no CI history |
| Solutions Engineer / Architect | H1, H2, the written contracts and ADR-style docstrings | no customer-facing deployment |
