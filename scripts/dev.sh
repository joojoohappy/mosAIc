#!/usr/bin/env bash
# Start both processes. Forgetting the backend is the dumbest and most common way to
# kill a demo. No --reload: one less moving part while presenting.
set -euo pipefail

# Docker Desktop squats :8000 on some machines. Override without editing this file:
#   BACKEND_PORT=8010 ./scripts/dev.sh
#
# NOT named PORT: `PORT=8010 ./scripts/dev.sh` exports PORT into this script's
# environment, and bash keeps that export through the `PORT=${PORT:-8000}`
# reassignment below -- so it would leak into the `next dev` child process too,
# and Next.js independently honours process.env.PORT and binds THERE instead
# of :3000. (Found by running exactly that and getting web on :8010 as well.)
BACKEND_PORT=${BACKEND_PORT:-8000}
cd "$(dirname "$0")/.."          # repo root

UV=apps/backend/.venv/bin/uvicorn
if [ ! -x "$UV" ]; then
  echo "no venv yet. run:"
  echo "  python3 -m venv apps/backend/.venv && apps/backend/.venv/bin/pip install -r apps/backend/requirements.txt"
  exit 1
fi

"$UV" app.main:app --port "$BACKEND_PORT" --app-dir apps/backend &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT

# Bounded wait that also notices a dead process — an unbounded `until curl` loop
# spins silently forever when the backend fails to boot.
up=""
for _ in $(seq 60); do
  if curl -sf "localhost:$BACKEND_PORT/api/health" >/dev/null 2>&1; then up=1; break; fi
  if ! kill -0 $API 2>/dev/null; then echo "backend exited during startup (see above)"; exit 1; fi
  sleep 0.25
done
[ -n "$up" ] || { echo "backend did not answer /api/health on :$BACKEND_PORT within 15s"; exit 1; }
echo "backend up on :$BACKEND_PORT"

if [ ! -f apps/web/package.json ]; then
  echo "apps/web/ has no package.json — running backend only. Ctrl-C to stop."
  wait $API
fi
# unset PORT explicitly: if the *caller's* shell happens to have PORT set for
# any other reason, don't let it silently redirect where web binds either.
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT" PORT= pnpm --filter @mosaic/web exec next dev --webpack -p 3000
