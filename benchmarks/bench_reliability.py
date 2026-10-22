"""B3: reliability and abuse-control scenarios against the real backend.

Each scenario starts a fresh backend (temp storage) wired to the local fake
provider, provokes one failure or edge case, and records what the API did:
status codes, result mode, fallback reason, wall time, how many (simulated)
paid provider calls were made, and the daily-budget counter.

All "provider" behaviour is SIMULATED by fake_gemini.py. Nothing here is a
statement about how real Gemini fails.

    apps/backend/.venv/bin/python benchmarks/bench_reliability.py [--only NAME]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import time

import httpx

from harness import Backend, FakeProvider, environment, free_port, jpeg, save

PHOTO = jpeg(640, 480)
OPEN = {"MOSAIC_RATE_PER_MINUTE": "100000", "MOSAIC_DAILY_PER_CLIENT": "100000",
        "MOSAIC_DAILY_GLOBAL": "100000", "MOSAIC_MAX_CONCURRENT": "1000"}


def post(be, photo=PHOTO, headers=None, timeout=120):
    t0 = time.perf_counter()
    r = httpx.post(be.url + "/api/generate", data={"recipeId": "seed-01"},
                   files={"image": ("p.jpg", photo, "image/jpeg")},
                   headers=headers or {}, timeout=timeout)
    wall = time.perf_counter() - t0
    try:
        body = r.json()
    except ValueError:  # e.g. a plain-text 500 from an unhandled exception
        body = {"error": "non_json:" + r.text[:40]}
    out = {"status": r.status_code, "wall_s": round(wall, 2), "error": body.get("error")}
    if "resultId" in body:
        res = httpx.get(f"{be.url}/api/results/{body['resultId']}").json()
        out.update(resultId=body["resultId"], mode=res["mode"],
                   fallbackReason=res["fallbackReason"])
    return out


def uniq(i):
    return PHOTO + f"\x00u{i}-{time.time_ns()}".encode()


def env(fake, **extra):
    return {"GEMINI_API_KEY": "bench-fake-key", "MOSAIC_PROVIDER_ENDPOINT": fake.endpoint,
            "MOSAIC_PROVIDER_TIMEOUT": "2", **OPEN, **extra}


# --- scenarios -------------------------------------------------------------

def provider_failures(fake):
    """One request per simulated provider failure mode, provider timeout = 2 s."""
    cases = [("ok", 0, "live"), ("error", 0, "fallback"), ("hang", 5, "fallback within ~2 s"),
             ("text", 0, "fallback"), ("badjson", 0, "fallback"),
             ("drip", 0.1, "fallback within ~2 s"), ("refused", 0, "fallback")]
    rows = []
    for mode, delay, expect in cases:
        e = env(fake)
        if mode == "refused":
            e["MOSAIC_PROVIDER_ENDPOINT"] = f"http://127.0.0.1:{free_port()}/v1beta/interactions"
        else:
            fake.set(mode, delay)
        with Backend(e) as be:
            fake.reset()
            r = post(be, uniq(mode))
            r.update(case=mode, expected=expect,
                     provider_calls=fake.calls() if mode != "refused" else 0,
                     budget=be.usage_file())
            rows.append(r)
            print(f"provider={mode:8} status={r['status']} mode={r.get('mode')} "
                  f"reason={r.get('fallbackReason')} wall={r['wall_s']}s")
    fake.set("ok", 0)
    return rows


def duplicates(fake):
    """The same photo + recipe sent twice: at once, and 1 s apart while the first
    is still running, and after the first finished."""
    fake.set("ok", 3.0)
    rows = []
    for label, gap in [("simultaneous", 0.0), ("1s apart (refresh + retry)", 1.0),
                       ("after first finished", 3.5)]:
        with Backend(env(fake, MOSAIC_PROVIDER_TIMEOUT="10")) as be:
            fake.reset()
            photo = uniq(label)
            with cf.ThreadPoolExecutor(2) as pool:
                f1 = pool.submit(post, be, photo)
                time.sleep(gap)
                f2 = pool.submit(post, be, photo)
                a, b = f1.result(), f2.result()
            row = {"case": label, "provider_calls": fake.calls(),
                   "same_result": a.get("resultId") == b.get("resultId"),
                   "first": a, "second": b, "budget": be.usage_file()}
            rows.append(row)
            print(f"duplicate {label:28} provider_calls={row['provider_calls']} "
                  f"same_result={row['same_result']}")
    fake.set("ok", 0)
    return rows


def rate_limits(fake):
    """Default per-visitor limit (3/min) and a forged X-Forwarded-For per request."""
    fake.set("ok", 0)
    e = env(fake)
    e.pop("MOSAIC_RATE_PER_MINUTE")
    with Backend(e) as be:
        statuses = [post(be, uniq(i), headers={"X-Forwarded-For": f"10.0.0.{i}"})["status"]
                    for i in range(6)]
    print(f"rate limit with forged XFF: {statuses}")
    return {"case": "6 requests, 6 different forged X-Forwarded-For, default 3/min",
            "statuses": statuses}


def daily_budget(fake):
    fake.set("ok", 0)
    with Backend(env(fake, MOSAIC_DAILY_GLOBAL="5")) as be:
        fake.reset()
        res = [post(be, uniq(i)) for i in range(8)]
        row = {"case": "MOSAIC_DAILY_GLOBAL=5, 8 sequential distinct requests",
               "statuses": [r["status"] for r in res], "errors": [r["error"] for r in res],
               "provider_calls": fake.calls(), "budget": be.usage_file()}
    print(f"budget sequential: {row['statuses']} provider_calls={row['provider_calls']}")
    return row


def budget_race(fake, trials=5):
    """Global daily budget under sustained parallel load with several worker
    processes sharing one local store (read-modify-write of usage-<day>.json).

    Shipped default MOSAIC_MAX_CONCURRENT=2 per process. limits.py documents an
    overshoot of at most MAX_CONCURRENT per instance, i.e. <= 8 with 4 workers.
    """
    fake.set("ok", 0.05)
    rows = []
    for workers in (1, 4):
        for t in range(trials):
            e = env(fake, MOSAIC_DAILY_GLOBAL="50", MOSAIC_MAX_CONCURRENT="2")
            with Backend(e, workers=workers) as be:
                fake.reset()
                with cf.ThreadPoolExecutor(16) as pool:
                    res = list(pool.map(lambda i, t=t: post(be, uniq(f"r{t}-{i}")), range(300)))
                ok = sum(r["status"] == 200 for r in res)
                statuses: dict[str, int] = {}
                for r in res:
                    key = str(r["status"]) + (f":{r['error']}" if r["error"] else "")
                    statuses[key] = statuses.get(key, 0) + 1
                log = be.server_log()
                last_exc = [ln for ln in log.splitlines()
                            if "Error:" in ln and not ln.startswith(" ")][-1:]
                rows.append({"workers": workers, "trial": t + 1, "limit": 50,
                             "max_concurrent_per_worker": 2, "requests": 300,
                             "provider_calls": fake.calls(), "served_200": ok,
                             "statuses": statuses, "server_tracebacks": log.count("Traceback"),
                             "last_exception": last_exc[0][:160] if last_exc else None,
                             "budget_file": be.usage_file()})
                print(f"budget race workers={workers} trial={t+1} limit=50 "
                      f"provider_calls={fake.calls()} statuses={statuses} "
                      f"tracebacks={log.count('Traceback')} counter={be.usage_file()}")
    fake.set("ok", 0)
    return rows


def body_limits(fake):
    """Oversized bodies: declared Content-Length, and chunked with no length.
    Both are well-formed multipart uploads of a 9 MB file part."""
    head = (b"--x\r\nContent-Disposition: form-data; name=\"recipeId\"\r\n\r\nseed-01\r\n"
            b"--x\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.jpg\"\r\n"
            b"Content-Type: image/jpeg\r\n\r\n\xff\xd8\xff")
    tail = b"\r\n--x--\r\n"
    big = head + b"\0" * (9 * 1024 * 1024) + tail
    ctype = {"Content-Type": "multipart/form-data; boundary=x"}
    with Backend(env(fake)) as be:
        r1 = httpx.post(be.url + "/api/generate", content=big, headers=ctype)

        def chunks():
            for i in range(0, len(big), 256 * 1024):
                yield big[i:i + 256 * 1024]
        r2 = httpx.post(be.url + "/api/generate", content=chunks(), headers=ctype)
        alive = httpx.get(be.url + "/api/health").status_code
    row = {"declared_9MB": [r1.status_code, r1.text[:40]],
           "chunked_9MB": [r2.status_code, r2.text[:40]], "health_after": alive}
    print(f"body limits: {row}")
    return row


def corrupt_uploads(fake):
    """Damaged photos: do they reach the (paid) provider?"""
    fake.set("ok", 0)
    base = jpeg(2048, 1536)
    corpus = {f"jpeg truncated to {int(f*100)}%": base[:int(len(base) * f)]
              for f in (0.99, 0.9, 0.5, 0.1, 0.01)}
    mid = bytearray(base)
    mid[len(mid) // 2: len(mid) // 2 + 20000] = b"\x00" * 20000
    corpus["jpeg 20KB zeroed mid-file"] = bytes(mid)
    corpus["valid jpeg (control)"] = base
    rows = []
    with Backend(env(fake)) as be:
        for name, data in corpus.items():
            fake.reset()
            r = post(be, data + f"\x00{name}".encode() if name.startswith("valid") else data)
            rows.append({"case": name, "status": r["status"], "error": r["error"],
                         "reached_provider": fake.calls() > 0})
            print(f"upload {name:28} status={r['status']} reached_provider={fake.calls() > 0}")
    return rows


def restart_recovery(fake):
    """A result survives a graceful and a hard restart (local store)."""
    fake.set("ok", 0)
    with Backend(env(fake)) as be:
        rid = post(be, uniq("restart"))["resultId"]
        soft = be.restart(hard=False)
        after_soft = httpx.get(f"{be.url}/api/results/{rid}").status_code
        hard = be.restart(hard=True)
        after_hard = httpx.get(f"{be.url}/api/results/{rid}").status_code
    row = {"restart_to_healthy_s": {"sigterm": round(soft, 2), "sigkill": round(hard, 2)},
           "result_after_sigterm": after_soft, "result_after_sigkill": after_hard}
    print(f"restart: {row}")
    return row


SCENARIOS = {
    "provider_failures": provider_failures, "duplicates": duplicates,
    "rate_limits": rate_limits, "daily_budget": daily_budget, "budget_race": budget_race,
    "body_limits": body_limits, "corrupt_uploads": corrupt_uploads,
    "restart_recovery": restart_recovery,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append")
    ap.add_argument("--tag", default="reliability")
    args = ap.parse_args()
    fake = FakeProvider()
    out = {"benchmark": "B3 reliability scenarios (SIMULATED provider)",
           "environment": environment()}
    for name, fn in SCENARIOS.items():
        if args.only and name not in args.only:
            continue
        out[name] = fn(fake)
    fake.close()
    save(args.tag, out)


if __name__ == "__main__":
    main()
