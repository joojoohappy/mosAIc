"""B2: POST /api/generate with a simulated provider.

The model is the local fake (fake_gemini.py). Real Gemini latency is NOT
measured here; what is measured is everything MOSAIC itself does around the
model call: multipart parsing, magic-byte + Pillow validation, fingerprinting,
the limits, base64/JSON request building, result writes.

Parts:
  overhead   provider delay 0, concurrency 1, photo sizes 0.3 / 3 / 12 MP.
             Latency here is MOSAIC's own per-request cost.
  shedding   provider delay 2 s, MOSAIC_MAX_CONCURRENT=2 (the shipped default),
             10 / 20 simultaneous distinct uploads: how many are served vs 503.
  memory     provider delay 1 s, 8 MB-class uploads at concurrency 1 / 4 / 16,
             peak RSS of the uvicorn process.

    apps/backend/.venv/bin/python benchmarks/bench_generate.py [--quick]
"""

from __future__ import annotations

import argparse
import asyncio
import time

from harness import (Backend, FakeProvider, ProcSampler, closed_loop, environment,
                     jpeg, save, summarize)

OPEN_LIMITS = {
    "MOSAIC_RATE_PER_MINUTE": "1000000",
    "MOSAIC_DAILY_PER_CLIENT": "1000000",
    "MOSAIC_DAILY_GLOBAL": "1000000",
    "MOSAIC_MAX_CONCURRENT": "1000",
}


def unique(photo: bytes, i: int) -> bytes:
    # Bytes after the JPEG end marker are ignored by decoders but change the
    # fingerprint, so the 10-minute duplicate cache never short-circuits a run.
    return photo + b"\x00bench" + str(i).encode() + str(time.time_ns()).encode()


def generate_sender(url: str, photo: bytes, tag: str):
    async def send(client, i):
        r = await client.post(url + "/api/generate", data={"recipeId": "seed-01"},
                              files={"image": (f"{tag}{i}.jpg", unique(photo, i), "image/jpeg")})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return r.status_code, {"error": body.get("error")}
    return send


def overhead(fake, quick):
    fake.set("ok", 0)
    sizes = {"0.3MP 640x480": (640, 480), "3MP 2048x1536": (2048, 1536),
             "12MP 4032x3024": (4032, 3024)}
    n = 20 if quick else 100
    reps = 1 if quick else 3
    cells = []
    env = {"GEMINI_API_KEY": "bench-fake-key", "MOSAIC_PROVIDER_ENDPOINT": fake.endpoint,
           **OPEN_LIMITS}
    with Backend(env) as be:
        for label, (w, h) in sizes.items():
            photo = jpeg(w, h)
            send = generate_sender(be.url, photo, label)
            asyncio.run(closed_loop(send, 5, 1))  # warm-up
            for rep in range(1, reps + 1):
                with ProcSampler(be.proc.pid) as ps:
                    samples, wall = asyncio.run(closed_loop(send, n, 1))
                s = summarize(samples, wall)
                s.update(photo=label, bytes=len(photo), rep=rep,
                         server_cpu_ms_per_req=round(ps.cpu_seconds * 1000 / n, 1),
                         server_rss_peak_mb=round(ps.rss_peak_mb, 1))
                cells.append(s)
                print(f"overhead {label:16} {len(photo)/1e6:5.2f}MB rep={rep} p50={s['p50_ms']:7.1f} "
                      f"p95={s['p95_ms']:7.1f} cpu/req={s['server_cpu_ms_per_req']}ms")
    return cells


def shedding(fake, quick):
    fake.set("ok", 2.0)
    cells = []
    photo = jpeg(640, 480)
    for burst in ([10] if quick else [10, 20]):
        env = {"GEMINI_API_KEY": "bench-fake-key", "MOSAIC_PROVIDER_ENDPOINT": fake.endpoint,
               **OPEN_LIMITS, "MOSAIC_MAX_CONCURRENT": "2"}
        with Backend(env) as be:
            fake.reset()
            samples, wall = asyncio.run(closed_loop(generate_sender(be.url, photo, "shed"),
                                                    burst, burst))
            s = summarize(samples, wall)
            served = [x["latency_ms"] for x in samples if x["status"] == 200]
            shed = [x["latency_ms"] for x in samples if x["status"] == 503]
            s.update(burst=burst, provider_calls=fake.calls(),
                     served_p50_ms=round(sorted(served)[len(served) // 2], 1) if served else None,
                     shed_max_ms=round(max(shed), 1) if shed else None,
                     errors=sorted({str(x.get("error")) for x in samples}))
            cells.append(s)
            print(f"shedding burst={burst} statuses={s['statuses']} provider_calls={s['provider_calls']}"
                  f" served_p50={s['served_p50_ms']} shed_max={s['shed_max_ms']}")
    return cells


def memory(fake, quick):
    fake.set("ok", 1.0)
    photo = jpeg(4032, 3024, quality=97)  # ~ the largest class of phone photo
    cells = []
    for conc in ([1, 4] if quick else [1, 4, 16]):
        env = {"GEMINI_API_KEY": "bench-fake-key", "MOSAIC_PROVIDER_ENDPOINT": fake.endpoint,
               **OPEN_LIMITS}
        with Backend(env) as be:
            with ProcSampler(be.proc.pid, interval=0.02) as ps:
                samples, wall = asyncio.run(closed_loop(generate_sender(be.url, photo, "mem"),
                                                        conc * 2, conc))
            s = summarize(samples, wall)
            s.update(concurrency=conc, upload_mb=round(len(photo) / 1e6, 2),
                     rss_idle_mb=round(ps.rss_start_mb, 1), rss_peak_mb=round(ps.rss_peak_mb, 1),
                     rss_growth_mb=round(ps.rss_peak_mb - ps.rss_start_mb, 1))
            cells.append(s)
            print(f"memory c={conc:<3} upload={s['upload_mb']}MB idle={s['rss_idle_mb']}MB "
                  f"peak={s['rss_peak_mb']}MB statuses={s['statuses']}")
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--tag", default="generate")
    args = ap.parse_args()
    fake = FakeProvider()
    out = {
        "benchmark": "B2 generate pipeline (SIMULATED provider: local fake, not Gemini)",
        "environment": environment(),
        "overhead": overhead(fake, args.quick),
        "shedding": shedding(fake, args.quick),
        "memory": memory(fake, args.quick),
    }
    fake.close()
    save(args.tag, out)


if __name__ == "__main__":
    main()
