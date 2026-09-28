# MOSAIC

The first web frontend implements the approved Figma screens using Next.js App Router, React, TypeScript, and ordinary CSS. FastAPI remains the sole API owner. Shared client/types are ready to be consumed by a future Expo app.

| Directory         | Responsibility                                                 |
| ----------------- | -------------------------------------------------------------- |
| `apps/web`        | Website, routes, React components, same-origin rewrites        |
| `apps/mobile`     | Preserved Expo placeholders; not a runnable app yet            |
| `apps/backend`    | Existing FastAPI code, seed data, storage and tests            |
| `packages/api`    | Framework-independent TypeScript API client and error mapping  |
| `packages/types`  | Existing public backend contracts                              |
| `packages/core`   | Cross-platform upload validation                               |
| `packages/design` | Shared design tokens                                           |
| `content/recipes` | Reserved editorial content; not a second runtime recipe source |
| `docs`            | Product, design and architecture notes                         |

The migration changes directory locations and developer commands. Backend pipeline behavior, public fields, unverified attribution and readiness settings are preserved. The previous hosted static prototype remains a historical preview; this workspace is the backend-connected frontend source.
