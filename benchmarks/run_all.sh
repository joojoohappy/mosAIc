#!/usr/bin/env bash
# Run every MOSAIC benchmark against the current checkout, or against another
# checkout's apps/backend via MOSAIC_BENCH_SRC (how the "baseline" numbers
# were produced from PR #2's head, fbbc625).
#
#   bash benchmarks/run_all.sh after                 # tag suffix for result files
#   MOSAIC_BENCH_SRC=/path/to/old/apps/backend bash benchmarks/run_all.sh baseline
#
# Needs: apps/backend/.venv (pip install -r apps/backend/requirements-dev.txt),
# k6 on PATH or K6=/path/to/k6. About 25 minutes on a 4-vCPU machine.
set -euo pipefail
cd "$(dirname "$0")"
TAG=${1:-run}
PY=../apps/backend/.venv/bin/python
$PY bench_api.py --tag "api_latency_$TAG" | tee "results/api_latency_$TAG.log"
$PY bench_generate.py --tag "generate_$TAG" | tee "results/generate_$TAG.log"
$PY bench_reliability.py --tag "reliability_$TAG" | tee "results/reliability_$TAG.log"
$PY bench_stages.py --tag "stages_$TAG" | tee "results/stages_$TAG.log"
$PY compare_validation.py | tee results/validation_alternatives.log
