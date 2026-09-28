# Validation — 2026-09-28

- Next.js production build and strict TypeScript check passed on Node.js 24 / Windows ARM64.
- 9 frontend API/upload tests passed: multipart fields, 75-second generation timeout, no automatic retries, seven API errors, health diagnosis, malformed data, result modes, 8MB boundary.
- All 36 original backend pipeline tests passed after migration. A test-only Windows temp-directory permission adapter was required in this sandbox; backend source was not modified.
- Real FastAPI + Next.js proxy verified public recipe list/detail, `tryReady: false`, original source links, `/static`, and the offline `後端未啟動` message with recovery.
- An isolated FastAPI QA process enabled readiness only in memory and used a test image/provider. Verified real multipart upload, disabled controls during generation, result navigation, refresh, persisted results and static image serving. Live/cached/mock rendering displayed the backend note verbatim, hid diagnostic `fallbackReason`, and disabled mock downloads.
- Desktop and 390px mobile layouts checked in the browser. No horizontal overflow on checked mobile pages; no frontend console errors during normal flow.
- All 15 relocated backend files match the original Git blob hashes. Original readiness and provider implementation remain unchanged. QA uploads/results are outside the deliverable.

The isolated live fixture verifies integration behavior; it does not verify a real AI provider. Production deployment and real image generation remain backend/deployment follow-ups.
