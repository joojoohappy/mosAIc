# API contract

How the web app talks to the FastAPI backend. Checked against the source on 2026-10-22 (v0.1 release candidate).

## Transport

The web app uses same-origin `/api/*` and `/static/*`. `apps/web/next.config.ts` rewrites both prefixes to the server-only `BACKEND_URL` (default `http://127.0.0.1:8000`, read at build time). There must be no route handlers under `apps/web/app/api/`, which would shadow FastAPI. Do not statically export this app: it needs a Next.js server or a deployment reverse proxy with these routes. API keys remain exclusively in the backend environment.

The backend sends no CORS headers on purpose: browsers only ever talk to the website's own origin, so other sites cannot call the API from a visitor's browser. Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are disabled.

`apps/web/proxy.ts` runs before `POST /api/generate` is forwarded. It removes any `x-mosaic-client-ip` / `x-mosaic-proxy-secret` headers a browser sent and, when `MOSAIC_PROXY_SECRET` is set, adds them itself from the hosting platform's `x-real-ip` (see [Limits](#limits-and-cost-controls)).

| Endpoint                      | Response / request                                                                                  |
| ----------------------------- | --------------------------------------------------------------------------------------------------- |
| `GET /api/health`             | `{ "ok": true, "liveGeneration": boolean }`                                                         |
| `GET /api/recipes`            | `{ "recipes": PublicRecipe[] }`                                                                     |
| `GET /api/recipes/{id}`       | `PublicRecipe`                                                                                      |
| `POST /api/generate`          | Multipart `recipeId` + one `image`; response `{ "resultId": "32 lowercase hex characters" }`        |
| `GET /api/results/{resultId}` | `GenerationResult`                                                                                  |
| `GET /static/results/{name}`  | The result image (`<resultId>.png/jpg/webp`), `Cache-Control: private, max-age=86400, immutable`    |
| `GET /static/seed/{file}`     | Creator preview images that have been cleared for display. Nothing else under `storage/` is served. |

`liveGeneration` is `false` when there is no `GEMINI_API_KEY`, or when the backend runs on Vercel without a Blob store (see [Storage](#storage-and-retention)). The Create page then tells the visitor up front that results will be examples.

## Relation to the original contract

The first design sketch described `GET /recipes`, `GET /recipes/{id}` and `POST /generate` returning `generation_id`, `status` and `result_image_url`. v0.1 keeps the same shape with these deliberate differences:

| Original                    | v0.1                                  | Why                                                                                   |
| --------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------- |
| `/recipes`, `/generate`     | `/api/recipes`, `/api/generate`       | One prefix for the website to proxy; pages own every other path.                      |
| `generation_id`             | `resultId`                            | Same role: the id of the stored result, used in `/result/{resultId}` share links.     |
| `status` (pending/done/...) | none; generation is synchronous       | The POST returns only when the result is stored. No polling, no half-finished states. |
| `status` (how it was made)  | `mode`: `live` / `cached` / `mock`    | Tells the visitor honestly whether the image came from their photo.                   |
| `result_image_url`          | `imageUrl` in `GET /api/results/{id}` | Fetched with the result so a refreshed or shared page shows the same thing.           |

## Recipes

`packages/types` mirrors the public projection in `apps/backend/app/recipes.py`: `id, title, summary, category, tags, sourcePostUrl, creatorName, creatorInstagramUrl, previewBeforeUrl, previewImageUrl, inputNote, aspectRatio, promptVisibility, tryReady`, plus `prompt`. Recipe data is fetched at runtime. Never import the backend recipe JSON into web/mobile code, send a prompt, or fabricate an unverified creator.

`prompt` is the creator's full text when `promptVisibility` is `public`, and `null` otherwise. A hidden prompt never leaves the server: not in the API, not in the client bundle (the web app has no copy of `recipes.json`), not in results and not in logs. Generation always looks the prompt up by `recipeId`.

A null creator displays `來源待確認` with the original post link. A null preview displays the designed placeholder.

## Generation

- JPEG / PNG / WebP, nonempty, maximum `8 * 1024 * 1024` bytes. The server checks the actual content (magic bytes, then a full decode with Pillow and a 40-megapixel cap); the file name and declared type are ignored. iPhone HEIC photos are refused with a hint to convert them.
- Request bodies above 8.5 MB are refused with 413 before they are parsed. The browser shrinks photos over 4 MB (to JPEG, longest side 2048 px) before upload, because Vercel functions accept at most 4.5 MB.
- `tryReady: false` disables Try and Create, including direct navigation to the Create page, and the API answers 403 `recipe_not_ready`.
- Synchronous POST may take up to 60 seconds. Both browser and Next.js proxy allow 75 seconds. The page shows loading and locks repeated submissions. No polling, automatic retry, or fabricated result.
- The same recipe and the same photo within 10 minutes return the earlier `resultId` without a second model call (double click, refresh mid-generation, resubmit).
- Navigate to `/result/{resultId}` and fetch the persisted result. Refreshing retrieves it again.

| mode     | Presentation                                                                                              |
| -------- | --------------------------------------------------------------------------------------------------------- |
| `live`   | Display the generated image and server `sourceNote`.                                                      |
| `cached` | Display the pre-generated image with a prominent disclosure. Never claim it came from the current upload. |
| `mock`   | Show an empty result layout and the server note; no broken image and no enabled download.                 |

Always render `sourceNote` verbatim. Do not show `fallbackReason` to users; it is one of `no_api_key`, `no_shared_storage`, `provider_timeout`, `provider_no_image`, `provider_error`. Provider error details stay in the server log.

The uploaded photo is sent to the model and never written to storage. Local object URLs are revoked when replaced or unmounted. Saved favorites are device-local.

## Errors

| HTTP | code                   | UI message (packages/api `errorMessages`)                    |
| ---- | ---------------------- | ------------------------------------------------------------ |
| 400  | `missing_recipe_id`    | 未取得 recipe 資料，請返回探索頁重新選擇。                   |
| 400  | `missing_image`        | 請先選一張照片                                               |
| 400  | `unsupported_type`     | 只支援 JPEG / PNG / WebP（iPhone 的 HEIC 照片請先轉成 JPEG） |
| 400  | `invalid_image`        | 這張照片無法讀取，請換一張再試。                             |
| 413  | `too_large`            | 照片請小於 8MB                                               |
| 403  | `recipe_not_ready`     | 這份 recipe 尚未開放試用                                     |
| 404  | `unknown_recipe`       | 找不到這份 recipe                                            |
| 404  | `unknown_result`       | 結果不存在或連結已失效                                       |
| 429  | `rate_limited`         | 操作太頻繁了，請等一分鐘再試。                               |
| 429  | `daily_limit_reached`  | 你今天的免費生成次數已用完，明天再來試試。                   |
| 503  | `daily_budget_reached` | 今天的生成額度已用完，請明天再試。                           |
| 503  | `server_busy`          | 目前使用的人比較多，請稍後再試。                             |

Any 413 (including one from the hosting platform, which has no JSON body) maps to `too_large`. On network/proxy failure the client checks `/api/health`; if unreachable it shows `後端未啟動`. Timeouts and unexpected payloads have their own messages. A failed generation is never automatically re-submitted.

## Limits and cost controls

All limits are environment variables on the backend with conservative defaults. They are placeholders until the product decides its free tier.

| Variable                  | Default | Meaning                                          | Error when hit             |
| ------------------------- | ------- | ------------------------------------------------ | -------------------------- |
| `MOSAIC_RATE_PER_MINUTE`  | 3       | Generations per visitor per minute               | 429 `rate_limited`         |
| `MOSAIC_DAILY_PER_CLIENT` | 10      | Generations per visitor per UTC day              | 429 `daily_limit_reached`  |
| `MOSAIC_DAILY_GLOBAL`     | 50      | Paid model calls per UTC day across all visitors | 503 `daily_budget_reached` |
| `MOSAIC_MAX_CONCURRENT`   | 2       | Model calls running at once, per server instance | 503 `server_busy`          |

Order of checks in `POST /api/generate`: recipe exists → recipe is ready → image present, size, content → duplicate (free) → per-visitor limits → concurrency → global daily budget → model call.

**Who is a visitor.** `X-Forwarded-For` is never trusted, since any client can send one. The backend uses, in order: `x-mosaic-client-ip` when it arrives with the matching `MOSAIC_PROXY_SECRET` (set by `apps/web/proxy.ts` from the platform's `x-real-ip`); `x-real-ip` on Vercel or with `MOSAIC_TRUST_X_REAL_IP=1`; otherwise the socket address. When none of these identify the visitor, everyone shares one bucket. That is stricter than intended, never looser.

**Where counts live.** Per-visitor and concurrency counters are in memory, so each server instance enforces them separately. The global daily budget is stored with the results (local disk or Vercel Blob) and is shared by every instance. It is a read-then-write counter, not an atomic one: under parallel load on several instances it can overshoot by a few calls. The hard guarantee is the spending cap set with the model provider (Google AI Studio), which the release checklist requires.

## Storage and retention

| Where it runs               | Results and usage counters stored in     | Live generation                    |
| --------------------------- | ---------------------------------------- | ---------------------------------- |
| Local dev, Docker           | `apps/backend/storage/results/`, `meta/` | On when `GEMINI_API_KEY` is set    |
| Vercel with a Blob store    | Vercel Blob, `results/` and `meta/`      | On when `GEMINI_API_KEY` is set    |
| Vercel without a Blob store | `/tmp` of one instance (lost on restart) | **Off**: falls back to cached/mock |

Blob objects are stored `private` by default (`BLOB_ACCESS`), and images are always served through `/static/results/{name}`, so the Blob URL is never given to browsers. A result is reachable only by its unguessable 32-hex id; nothing lists results. Sharing is an explicit action on the result page.

Results older than `MOSAIC_RESULT_RETENTION_DAYS` (default 30) are no longer served (404 `unknown_result`). They are not yet deleted from storage automatically; scheduled deletion is on the v0.2 backlog.

## Image provider

`apps/backend/app/provider.py` calls a Google Gemini image model through the Interactions REST API (`POST https://generativelanguage.googleapis.com/v1beta/interactions`, key in the `x-goog-api-key` header) with the recipe prompt, the uploaded photo and the recipe's `aspectRatio`. Default model `gemini-nano-banana-2.1` (`MOSAIC_IMAGE_MODEL`). It has a hard deadline (`MOSAIC_PROVIDER_TIMEOUT`, 60 s max), no retries and no filesystem access. The endpoint is fixed in code; no user input can change where requests go.

Without a key every request falls back to `cached` (if a pre-generated sidecar exists in `storage/fallback/`) or `mock`.

## Current state

All three seeds are `tryReady: false` until their creators and usage basis are verified, so `POST /api/generate` returns 403 for them. The Gemini integration is covered by tests against a fake model server only; it has not yet been run with a real key.
