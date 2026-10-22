#!/usr/bin/env bash
# Run every automated check, in order, and print a summary.
#
#   bash scripts/test-all.sh            # everything
#   SKIP_E2E=1 bash scripts/test-all.sh # skip the browser tests
#
# Setup (once): pnpm install; python3 -m venv apps/backend/.venv;
#   apps/backend/.venv/bin/pip install -r apps/backend/requirements-dev.txt;
#   pnpm exec playwright-core install chromium
set -uo pipefail
cd "$(dirname "$0")/.."
PY=apps/backend/.venv/bin/python

results=()
run() { # name command...
  local name=$1; shift
  echo; echo "▶ $name"
  if "$@"; then results+=("✔ $name"); else results+=("✖ $name"); fi
}

run "Format + TypeScript (pnpm lint)"      pnpm lint
run "Python lint (ruff)"                   bash -c "cd apps/backend && .venv/bin/ruff check ."
run "Backend unit tests"                   bash -c "cd apps/backend && .venv/bin/python -m unittest discover -s tests"
run "API status codes (test_api.sh)"       bash apps/backend/tests/test_api.sh
run "Web client + real upload tests"       pnpm test
run "Production build"                     pnpm build
if [ -z "${SKIP_E2E:-}" ]; then
  run "Browser journey (Playwright)"       pnpm test:e2e
fi

echo; echo "──── Summary ────"
printf '%s\n' "${results[@]}"
! printf '%s\n' "${results[@]}" | grep -q '^✖'
