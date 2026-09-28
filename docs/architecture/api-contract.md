# MOSAIC 前端對接

Implementation reference: [MOSAIC 前端對接](https://claude.ai/artifact/VKcqRCFHdSMFTxTCfqf7wA), checked against the FastAPI source on 2026-09-28.

## Transport

The web app uses same-origin `/api/*` and `/static/*`. `apps/web/next.config.ts` rewrites both prefixes to the server-only `BACKEND_URL` (default `http://127.0.0.1:8000`). There must be no route handlers under `apps/web/app/api/`, which would shadow FastAPI. Do not statically export this app: it needs a Next.js server or a deployment reverse proxy with these routes. API keys remain exclusively in the backend environment.

| Endpoint                      | Response / request                                                                           |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| `GET /api/health`             | `{ "ok": true }`                                                                             |
| `GET /api/recipes`            | `{ "recipes": PublicRecipe[] }`                                                              |
| `GET /api/recipes/{id}`       | `PublicRecipe`                                                                               |
| `POST /api/generate`          | Multipart `recipeId` + one `image`; response `{ "resultId": "32 lowercase hex characters" }` |
| `GET /api/results/{resultId}` | `GenerationResult`                                                                           |

`packages/types` preserves the existing public projection. Recipe data is fetched at runtime. Never import the backend recipe JSON into web/mobile code, send a prompt, or fabricate an unverified creator. A null creator displays `來源待確認` with the original post link. A null preview displays the designed image placeholder.

## Generation

- JPEG / PNG / WebP, nonempty, maximum `8 * 1024 * 1024` bytes. Server magic-byte validation is authoritative.
- `tryReady: false` disables Try and Create, including direct navigation to the Create page. Show `這份 recipe 尚未開放試用` as availability information.
- Synchronous POST may take up to 60 seconds. Both browser and Next.js proxy allow 75 seconds. Show loading; lock repeated submissions. No polling, automatic retry, or fabricated result.
- Navigate to `/result/{resultId}` and fetch the persisted result. Refreshing retrieves it again.

| mode     | Presentation                                                                                              |
| -------- | --------------------------------------------------------------------------------------------------------- |
| `live`   | Display the generated image and server `sourceNote`.                                                      |
| `cached` | Display the pre-generated image with a prominent disclosure. Never claim it came from the current upload. |
| `mock`   | Show an empty result layout and the server note; no broken image and no enabled download.                 |

Always render `sourceNote` verbatim. Do not show `fallbackReason` to users. Do not retain uploads outside the current page: local object URLs are revoked when replaced or unmounted. Saved favorites are explicitly device-local preferences.

## Errors

| HTTP | code                | UI                                                             |
| ---- | ------------------- | -------------------------------------------------------------- |
| 400  | `missing_recipe_id` | Return to Discover and reselect; an unexpected frontend state. |
| 400  | `missing_image`     | 請先選一張照片                                                 |
| 400  | `unsupported_type`  | 只支援 JPEG / PNG / WebP                                       |
| 400  | `too_large`         | 照片請小於 8MB                                                 |
| 403  | `recipe_not_ready`  | 這份 recipe 尚未開放試用; disable generation.                  |
| 404  | `unknown_recipe`    | 找不到這份 recipe                                              |
| 404  | `unknown_result`    | 結果不存在或連結已失效                                         |

On network/proxy failure, check `/api/health`; if unreachable, show `後端未啟動`. Unexpected payloads and timeouts have separate recovery messages. Failed generation is never automatically re-submitted.

## Current backend state

The three seeds remain `tryReady: false`. `_call_provider()` is still unimplemented. The frontend preserves these states; readiness/provider configuration must be completed by the backend owners before live generation can work. No readiness values or provider behavior were changed in this migration.
