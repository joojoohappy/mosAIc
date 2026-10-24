#!/usr/bin/env bash
# B4: container build and startup for the backend image (apps/backend/Dockerfile).
#
#   bash benchmarks/bench_deploy.sh [context-dir]
#
# context-dir defaults to apps/backend. In a sandbox whose HTTPS proxy needs an
# extra CA, pass a copy of apps/backend whose Dockerfile adds that CA (see
# docs/engineering-case-study/04-benchmark-results.md); the measured app is the same.
#
# Measures: cold (--no-cache, base image already pulled) and warm build time, image size, container start -> first
# 200 from /api/health (5 runs; SKIP_BUILD=1 reuses an existing image), restart -> healthy (3 runs), and whether the
# image declares a HEALTHCHECK. Writes benchmarks/results/deploy.json.
set -euo pipefail
cd "$(dirname "$0")/.."
CTX=${1:-apps/backend}
IMG=mosaic-backend:bench
OUT=benchmarks/results/deploy.json
mkdir -p benchmarks/results

now() { date +%s.%N; }
sec() { printf "%.3f" "$(echo "$1" | bc)"; }  # valid JSON numbers
wait_healthy() { # port -> seconds waited
  local t0; t0=$(now)
  until curl -sf "http://127.0.0.1:$1/api/health" >/dev/null 2>&1; do sleep 0.05; done
  echo "$(now) - $t0" | bc
}

if [ -n "${SKIP_BUILD:-}" ]; then
  # Use an existing mosaic-backend:bench image (e.g. when the registry rate-limits).
  cold_build=null; warm_build=null
else
  t0=$(now); docker build -q --no-cache -t $IMG "$CTX" >/dev/null; cold_build=$(sec "$(now) - $t0")
  t0=$(now); docker build -q -t $IMG "$CTX" >/dev/null; warm_build=$(sec "$(now) - $t0")
fi
size_mb=$(( $(docker image inspect $IMG --format '{{.Size}}') / 1024 / 1024 ))
healthcheck=$(docker image inspect $IMG --format '{{if .Config.Healthcheck}}yes{{else}}no{{end}}')

starts=()
for i in 1 2 3 4 5; do
  port=$((18000 + i))
  t0=$(now)
  cid=$(docker run -d -p 127.0.0.1:$port:8000 $IMG)
  until curl -sf "http://127.0.0.1:$port/api/health" >/dev/null 2>&1; do sleep 0.05; done
  starts+=("$(sec "$(now) - $t0")")
  docker rm -f "$cid" >/dev/null
done

port=18100
cid=$(docker run -d -p 127.0.0.1:$port:8000 $IMG)
wait_healthy $port >/dev/null
restarts=()
for i in 1 2 3; do
  t0=$(now)
  docker restart -t 10 "$cid" >/dev/null
  until curl -sf "http://127.0.0.1:$port/api/health" >/dev/null 2>&1; do sleep 0.05; done
  restarts+=("$(sec "$(now) - $t0")")
done
user=$(docker exec "$cid" id -u)
docker rm -f "$cid" >/dev/null

join() { local IFS=,; echo "$*"; }
cat > $OUT <<EOF
{
  "benchmark": "B4 backend container build and startup",
  "measuredAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "docker": "$(docker version --format '{{.Server.Version}}')",
  "context": "$CTX",
  "note": "${NOTE:-}",
  "cold_build_no_cache_s": $cold_build,
  "warm_rebuild_s": $warm_build,
  "image_size_mb": $size_mb,
  "image_declares_healthcheck": "$healthcheck",
  "container_runs_as_uid": $user,
  "start_to_healthy_s": [$(join "${starts[@]}")],
  "restart_to_healthy_s": [$(join "${restarts[@]}")]
}
EOF
cat $OUT
