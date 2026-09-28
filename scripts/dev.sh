#!/usr/bin/env bash
# Start both processes. Forgetting the backend is the dumbest and most common way to
# kill a demo. No --reload: one less moving part while presenting.
set -euo pipefail

# Docker Desktop squats :8000 on some machines. Override without editing this file:
#   PORT=8010 ./scripts/dev.sh   (then point next.config.js at the same port)
PORT=${PORT:-8000}
cd "$(dirname "$0")/.."          # repo root

UV=backend/.venv/bin/uvicorn
if [ ! -x "$UV" ]; then
  echo "no venv yet. run:"
  echo "  python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

"$UV" app.main:app --port "$PORT" --app-dir backend &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT

# Bounded wait that also notices a dead process — an unbounded `until curl` loop
# spins silently forever when the backend fails to boot.
up=""
for _ in $(seq 60); do
  if curl -sf "localhost:$PORT/api/health" >/dev/null 2>&1; then up=1; break; fi
  if ! kill -0 $API 2>/dev/null; then echo "backend exited during startup (see above)"; exit 1; fi
  sleep 0.25
done
[ -n "$up" ] || { echo "backend did not answer /api/health on :$PORT within 15s"; exit 1; }
echo "backend up on :$PORT"

if [ ! -f frontend/website/package.json ]; then
  echo "frontend/website/ has no package.json yet — running backend only. Ctrl-C to stop."
  wait $API
fi
cd frontend/website && npm run dev
