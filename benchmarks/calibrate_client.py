"""Is the load generator the bottleneck? Same server, same endpoint, two clients.

GET /api/health at concurrency 8 and 32, 1,000 requests x 3 reps, measured by
(a) the Python httpx AsyncClient loop in harness.closed_loop and (b) k6.
If (a) reports much higher latency while the server CPU stays low, (a) is
measuring itself. This is why bench_api.py uses k6.

    K6=/path/to/k6 apps/backend/.venv/bin/python benchmarks/calibrate_client.py
"""

from __future__ import annotations

import asyncio

from bench_api import run_k6
from harness import Backend, ProcSampler, closed_loop, environment, save, summarize


def main():
    rows = []
    with Backend() as be:
        url = be.url + "/api/health"

        async def send(client, i):
            r = await client.get(url)
            return r.status_code, None

        for conc in (8, 32):
            asyncio.run(closed_loop(send, 200, conc))
            run_k6(url, conc, 200)
            for rep in range(1, 4):
                with ProcSampler(be.proc.pid) as ps:
                    samples, wall = asyncio.run(closed_loop(send, 1000, conc))
                s = summarize(samples, wall)
                s.update(client="python httpx asyncio", concurrency=conc, rep=rep,
                         server_cpu_util=round(ps.cpu_util, 2))
                rows.append(s)
                with ProcSampler(be.proc.pid) as ps:
                    lat, st, rps = run_k6(url, conc, 1000)
                k = summarize([{"latency_ms": v, "status": x} for v, x in zip(lat, st, strict=False)], 0)
                k.update(client="k6", concurrency=conc, rep=rep, throughput_rps=round(rps, 1),
                         server_cpu_util=round(ps.cpu_util, 2))
                rows.append(k)
                for r in rows[-2:]:
                    print(f"{r['client']:22} c={conc:<3} rep={rep} p50={r['p50_ms']:7.2f} "
                          f"p99={r['p99_ms']:7.2f} rps={r['throughput_rps']:7.1f} "
                          f"server_cpu={r['server_cpu_util']}")
    save("client_calibration", {"benchmark": "Load-generator calibration (GET /api/health)",
                                "environment": environment(), "rows": rows})


if __name__ == "__main__":
    main()
