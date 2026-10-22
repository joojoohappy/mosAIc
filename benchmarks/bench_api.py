"""B1: latency and throughput of MOSAIC's read endpoints.

Workload: the endpoints every page view hits (health, recipe list, recipe detail,
result JSON, result image), served by one uvicorn worker on loopback, closed-loop
clients at concurrency 1 / 8 / 32. A warm-up batch per cell is discarded.

    apps/backend/.venv/bin/python benchmarks/bench_api.py            # full
    apps/backend/.venv/bin/python benchmarks/bench_api.py --quick    # smoke

Load is generated with k6 (set K6=/path/to/k6 if it is not on PATH).
Writes results/api_latency.json (summary) and results/api_latency_raw.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from harness import (RESULTS, Backend, FakeProvider, ProcSampler, environment, jpeg,
                     save, summarize)

K6 = os.environ.get("K6") or shutil.which("k6") or "k6"
K6_SCRIPT = Path(__file__).resolve().parent / "k6" / "read.js"


def run_k6(url: str, vus: int, iterations: int) -> tuple[list[float], list[int], float]:
    """Run k6 once; return per-request latencies (ms), statuses and request rate."""
    with tempfile.TemporaryDirectory() as tmp:
        raw, summary = Path(tmp) / "raw.csv", Path(tmp) / "summary.json"
        subprocess.run([K6, "run", "--quiet", "--no-usage-report", "--out", f"csv={raw}",
                        "--summary-export", str(summary), str(K6_SCRIPT)],
                       env={**os.environ, "TARGET": url, "VUS": str(vus),
                            "ITERATIONS": str(iterations)},
                       check=True, capture_output=True)
        lat, statuses = [], []
        with open(raw) as f:
            for row in csv.DictReader(f):
                if row["metric_name"] == "http_req_duration":
                    lat.append(float(row["metric_value"]))
                    statuses.append(int(row["status"] or 0))
        rps = json.loads(summary.read_text())["metrics"]["http_reqs"]["rate"]
    return lat, statuses, rps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--tag", default="api_latency")
    args = ap.parse_args()
    requests = 200 if args.quick else 1000
    warmup = 50 if args.quick else 200
    reps = 1 if args.quick else 3
    levels = [1, 8, 32]

    fake = FakeProvider()
    env = {"GEMINI_API_KEY": "bench-fake-key", "MOSAIC_PROVIDER_ENDPOINT": fake.endpoint}
    rows, cells = [], []
    with Backend(env) as be:
        # One live result (from the fake provider) so result endpoints have data.
        r = httpx.post(be.url + "/api/generate", data={"recipeId": "seed-01"},
                       files={"image": ("p.jpg", jpeg(640, 480), "image/jpeg")}, timeout=30)
        rid = r.json()["resultId"]
        image_url = httpx.get(f"{be.url}/api/results/{rid}").json()["imageUrl"]
        endpoints = {
            "GET /api/health": "/api/health",
            "GET /api/recipes": "/api/recipes",
            "GET /api/recipes/{id}": "/api/recipes/seed-02",
            "GET /api/results/{id}": f"/api/results/{rid}",
            "GET /static/results/{name}": image_url,
        }
        for name, path in endpoints.items():
            for conc in levels:
                run_k6(be.url + path, conc, warmup)  # warm-up, discarded
                for rep in range(1, reps + 1):
                    with ProcSampler(be.proc.pid) as ps:
                        lat, statuses, rps = run_k6(be.url + path, conc, requests)
                    samples = [{"latency_ms": v, "status": st} for v, st in zip(lat, statuses, strict=False)]
                    s = summarize(samples, 0)
                    s.update(endpoint=name, concurrency=conc, rep=rep,
                             throughput_rps=round(rps, 1),
                             server_cpu_util=round(ps.cpu_util, 2),
                             server_rss_peak_mb=round(ps.rss_peak_mb, 1))
                    cells.append(s)
                    rows += [(name, conc, rep, i, round(v, 3), st)
                             for i, (v, st) in enumerate(zip(lat, statuses, strict=False))]
                    print(f"{name:28} c={conc:<3} rep={rep} p50={s['p50_ms']:7.2f} "
                          f"p95={s['p95_ms']:7.2f} p99={s['p99_ms']:7.2f} "
                          f"rps={s['throughput_rps']:7.1f} cpu={s['server_cpu_util']}")
    fake.close()

    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / f"{args.tag}_raw.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["endpoint", "concurrency", "rep", "i", "latency_ms", "status"])
        w.writerows(rows)
    save(args.tag, {
        "benchmark": "B1 read-endpoint latency",
        "environment": environment(),
        "config": {"requests_per_rep": requests, "warmup_per_cell": warmup, "reps": reps,
                   "concurrency": levels, "uvicorn_workers": 1, "transport": "loopback HTTP/1.1",
                   "client": "k6 v1.3.0 shared-iterations, same machine as server; latency = k6 http_req_duration"},
        "cells": cells,
    })


if __name__ == "__main__":
    main()
