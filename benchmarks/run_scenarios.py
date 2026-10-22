"""Run every backend benchmark scenario and write raw + summary JSON.

    apps/backend/.venv/bin/python benchmarks/run_scenarios.py --label baseline
    apps/backend/.venv/bin/python benchmarks/run_scenarios.py --label after --only S2,S3

Each scenario starts its own isolated backend (benchmarks/run_backend.py), so
scenarios cannot contaminate each other. Results land in
benchmarks/raw/<label>/ (per-request samples) and benchmarks/results/<label>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import socket
import statistics
import subprocess
import sys
import time
import timeit
import urllib.error
import urllib.request
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PY = sys.executable
FIX = HERE / "fixtures"


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Backend:
    def __init__(self, *extra: str, src: str | None = None):
        self.port = free_port()
        cmd = [PY, str(HERE / "run_backend.py"), "--port", str(self.port), *extra]
        if src:
            cmd += ["--src", src]
        self.t0 = time.perf_counter()
        # Server output goes to a file, never an unread PIPE: the backend print()s one line per
        # generation, and a full 64 KB pipe buffer would block the server mid-benchmark.
        (HERE / "raw").mkdir(exist_ok=True)
        self.log = open(HERE / "raw" / "backend-last.log", "w")
        self.proc = subprocess.Popen(cmd, stdout=self.log, stderr=subprocess.STDOUT, text=True)
        self.base = f"http://127.0.0.1:{self.port}"
        deadline = time.time() + 30
        while True:
            try:
                urllib.request.urlopen(self.base + "/api/health", timeout=1).read()
                break
            except Exception:
                if self.proc.poll() is not None or time.time() > deadline:
                    raise RuntimeError("backend failed to start; see benchmarks/raw/backend-last.log")
                time.sleep(0.02)
        self.startup_ms = (time.perf_counter() - self.t0) * 1000
        self.ps = psutil.Process(self.proc.pid)

    def tmpdir(self) -> Path:
        # run_backend.py chdirs into its temp copy
        return Path(self.ps.cwd())

    def close(self):
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait()


def loadgen(url: str, conc: int, n: int, warm: int, out: Path, *extra: str) -> dict:
    cmd = ["node", str(HERE / "loadgen.mjs"), "--url", url, "--concurrency", str(conc), "--requests", str(n),
           "--warmup", str(warm), "--out", str(out), *extra]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])


def http(method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 120):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(); return r.status, body, (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, e.read(), (time.perf_counter() - t0) * 1000
    except Exception as e:  # timeout / reset
        return type(e).__name__, b"", (time.perf_counter() - t0) * 1000


def multipart(fields: dict, file_bytes: bytes, filename="photo.png") -> tuple[bytes, dict]:
    b = "----mosaicbench"
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode()
                 + file_bytes + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={b}"}


def dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


# --------------------------------------------------------------------------- scenarios

def s1_latency(raw: Path, src, trials=3) -> list[dict]:
    """API latency/throughput per endpoint and concurrency (no simulated provider)."""
    upload = str(FIX / "upload-photo-4032x3024.jpg")
    rows = []
    be = Backend("--ready", "seed-01", "--ready", "seed-03", "--fallback-bytes", "1500000", src=src)
    try:
        # One mock-mode recipe (seed-01 -> rename sidecar away) is awkward; instead: seed-03 has a
        # fallback (cached), seed-01's fallback is removed so it is mock, seed-02 is not ready (403).
        tmp = be.tmpdir()
        for f in (tmp / "storage" / "fallback").glob("seed-01.*"):
            f.unlink()
        data, hdr = multipart({"recipeId": "seed-01"}, (FIX / "upload-photo-4032x3024.jpg").read_bytes())
        st, body, _ = http("POST", be.base + "/api/generate", data, hdr)
        rid = json.loads(body)["resultId"]
        endpoints = [
            ("GET /api/health", be.base + "/api/health", []),
            ("GET /api/recipes", be.base + "/api/recipes", []),
            ("GET /api/recipes/{id}", be.base + "/api/recipes/seed-01", []),
            ("GET /api/results/{id}", be.base + f"/api/results/{rid}", []),
            ("POST /api/generate 403 not-ready", be.base + "/api/generate", ["--method", "POST", "--form", "recipeId=seed-02", "--file", f"image={upload}"]),
            ("POST /api/generate mock", be.base + "/api/generate", ["--method", "POST", "--form", "recipeId=seed-01", "--file", f"image={upload}"]),
            ("POST /api/generate cached(1.5MB asset)", be.base + "/api/generate", ["--method", "POST", "--form", "recipeId=seed-03", "--file", f"image={upload}"]),
        ]
        for name, url, extra in endpoints:
            post = bool(extra)
            for conc in (1, 8, 32):
                for t in range(trials):
                    n, w = (200, 20) if post else (1000, 100)
                    s = loadgen(url, conc, n, w, raw / f"s1-{''.join(c if c.isalnum() else '_' for c in name)}-c{conc}-t{t}.json", *extra, "--label", name)
                    rows.append({"endpoint": name, "concurrency": conc, "trial": t, **{k: s[k] for k in ("rps", "p50", "p95", "p99", "max", "statuses", "requests")}})
                    print(f"  S1 {name:40s} c={conc:<3d} t={t} rps={s['rps']:8.1f} p50={s['p50']:7.2f} p99={s['p99']:8.2f} {s['statuses']}", flush=True)
        rows.append({"rss_mb_after": round(be.ps.memory_info().rss / 2**20, 1), "results_dir_bytes": dir_bytes(tmp / "storage" / "results")})
    finally:
        be.close()
    return rows


def s2_head_of_line(raw: Path, src, sleep_s=5.0, trials=3) -> list[dict]:
    """Latency of ONE /api/health call issued while N simulated-provider generations are in flight.

    Two upload variants: a 1x1 PNG isolates the thread-pool effect; the 1.6 MB photo adds
    the cost of multipart parsing on the event loop."""
    rows = []
    tiny = HERE / "fixtures" / "tiny-1x1.png"
    if not tiny.exists():
        import base64
        tiny.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
    for upload in (tiny, FIX / "upload-photo-4032x3024.jpg"):
        for n in (0, 20, 39, 40, 41, 60):
            for t in range(trials):
                be = Backend("--ready", "seed-01", "--provider", f"sleep:{sleep_s}", src=src)
                try:
                    bg = None
                    if n:
                        bg = subprocess.Popen(["node", str(HERE / "loadgen.mjs"), "--url", be.base + "/api/generate", "--method", "POST",
                                               "--form", "recipeId=seed-01", "--file", f"image={upload}",
                                               "--concurrency", str(n), "--requests", str(n)], stdout=subprocess.PIPE, text=True)
                        # wait until the worker threads have been spawned (or 3 s), so the probe lands mid-generation
                        deadline, last, stable = time.time() + 3, -1, 0
                        while time.time() < deadline:
                            k = be.ps.num_threads()
                            stable = stable + 1 if k == last else 0
                            last = k
                            if k >= min(n, 40) + 1 and stable >= 3:
                                break
                            time.sleep(0.05)
                    threads = be.ps.num_threads()
                    st, _, ms = http("GET", be.base + "/api/health", timeout=60)
                    gen = json.loads(bg.communicate(timeout=180)[0].strip().splitlines()[-1]) if bg else None
                    row = {"upload": upload.name, "inflight": n, "trial": t, "provider_sleep_s": sleep_s, "health_status": st,
                           "health_ms": round(ms, 1), "server_threads_at_probe": threads,
                           "generate_wall_ms": gen["wallMs"] if gen else None, "generate_statuses": gen["statuses"] if gen else None}
                    rows.append(row)
                    print(f"  S2 {upload.name:28s} inflight={n:3d} t={t} health={ms:8.1f} ms threads={threads} gen_wall={row['generate_wall_ms']}", flush=True)
                finally:
                    be.close()
    return rows


def s3_upload_size(raw: Path, src) -> list[dict]:
    """Oversized uploads (PNG magic + zero padding), sent with curl WITHOUT `Expect: 100-continue`
    (browsers do not use it), so the client really tries to push the whole body."""
    rows = []
    be = Backend("--ready", "seed-01", src=src)
    try:
        for mb in (1, 8, 9, 64, 256):
            f = Path("/tmp") / f"mosaic-upload-{mb}mb.png"
            if not f.exists():
                f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * (mb * 2**20 - 8))
            for rid in ("seed-02", "seed-01"):
                runs = []
                for _ in range(3):
                    out = subprocess.run(["curl", "-s", "-H", "Expect:", "-o", "/dev/null", "-w", "%{http_code} %{time_total} %{size_upload}",
                                          "-F", f"recipeId={rid}", "-F", f"image=@{f}", be.base + "/api/generate"],
                                         capture_output=True, text=True).stdout.split()
                    runs.append((out[0], float(out[1]) * 1000, int(out[2])))
                row = {"upload_mb": mb, "recipe": rid, "tryReady": rid == "seed-01", "status": runs[0][0],
                       "median_ms": round(statistics.median(r[1] for r in runs), 1),
                       "bytes_sent_by_client": runs[0][2], "rss_mb_after": round(be.ps.memory_info().rss / 2**20, 1)}
                rows.append(row)
                print(f"  S3 {mb:4d} MB {rid} -> {row['status']} {row['median_ms']} ms sent={row['bytes_sent_by_client']} rss={row['rss_mb_after']}MB", flush=True)
    finally:
        be.close()
    return rows


def s4_hung_provider(raw: Path, src, client_timeout=20.0, k=5) -> dict:
    """A provider that never returns: what does the caller see, and what leaks?"""
    be = Backend("--ready", "seed-01", "--provider", "hang", src=src)
    try:
        body, hdr = multipart({"recipeId": "seed-01"}, (FIX / "upload-photo-4032x3024.jpg").read_bytes())
        t0 = threads0 = be.ps.num_threads()
        procs = [subprocess.Popen(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} %{time_total}", "-m", str(client_timeout),
                                   "-F", "recipeId=seed-01", "-F", f"image=@{FIX / 'upload-photo-4032x3024.jpg'}", be.base + "/api/generate"],
                                  stdout=subprocess.PIPE, text=True) for _ in range(k)]
        outs = [p.communicate()[0] for p in procs]
        time.sleep(1)
        threads_after = be.ps.num_threads()
        st, _, ms = http("GET", be.base + "/api/health", timeout=10)
        res = {"client_timeout_s": client_timeout, "requests": k, "client_results": outs,
               "server_threads_before": threads0, "server_threads_after_clients_gave_up": threads_after,
               "health_after": [st, round(ms, 1)]}
        print("  S4", json.dumps(res), flush=True)
        return res
    finally:
        be.close()


def s5_storage(raw: Path, src, n=100) -> list[dict]:
    rows = []
    for mode, extra in (("mock", []), ("cached", ["--fallback-bytes", "1500000"])):
        be = Backend("--ready", "seed-01", *extra, src=src)
        try:
            d = be.tmpdir() / "storage" / "results"
            before = dir_bytes(d)
            loadgen(be.base + "/api/generate", 4, n, 0, raw / f"s5-{mode}.json", "--method", "POST", "--form", "recipeId=seed-01",
                    "--file", f"image={FIX / 'upload-photo-4032x3024.jpg'}")
            after = dir_bytes(d)
            files = len(list(d.iterdir())) if d.exists() else 0
            rows.append({"mode": mode, "requests": n, "bytes_written": after - before, "bytes_per_request": (after - before) // n, "files": files})
            print(f"  S5 {mode}: {after - before} bytes for {n} requests ({(after - before)//n} B/req, {files} files)", flush=True)
        finally:
            be.close()
    return rows


def s6_startup(raw: Path, src, reps=10) -> dict:
    xs = []
    for _ in range(reps):
        be = Backend(src=src); xs.append(be.startup_ms); be.close()
    r = {"reps": reps, "median_ms": round(statistics.median(xs), 1), "min_ms": round(min(xs), 1), "max_ms": round(max(xs), 1),
         "note": "process spawn -> first 200 from /api/health, includes Python import of FastAPI/uvicorn"}
    print("  S6", r, flush=True)
    return r


def s7_recipe_load(src) -> dict:
    """Cost of re-reading recipes.json on every request (in-process micro-benchmark)."""
    sys.path.insert(0, str(Path(src)))
    from app import recipes as rmod  # type: ignore
    n = 2000
    per = min(timeit.repeat(rmod.load_recipes, number=n, repeat=5)) / n * 1e6
    r = {"load_recipes_us": round(per, 1), "file_bytes": rmod.RECIPES_FILE.stat().st_size}
    print("  S7", r, flush=True)
    return r


SCEN = {"S1": s1_latency, "S2": s2_head_of_line, "S3": s3_upload_size, "S4": s4_hung_provider,
        "S5": s5_storage, "S6": s6_startup}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--only", default=",".join(list(SCEN) + ["S7"]))
    ap.add_argument("--src", default=str(REPO / "apps" / "backend"))
    a = ap.parse_args()
    raw = HERE / "raw" / a.label; raw.mkdir(parents=True, exist_ok=True)
    out = HERE / "results" / f"{a.label}.json"
    results = json.loads(out.read_text()) if out.exists() else {}
    results["env"] = {"when": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "python": platform.python_version(), "platform": platform.platform(),
                      "cpus": os.cpu_count(), "cpu": platform.processor() or "see loadgen env", "mem_gb": round(psutil.virtual_memory().total / 2**30, 1),
                      "src": a.src, "note": "load generator and server share the same 2 vCPUs; loopback networking"}
    import fastapi, starlette, uvicorn  # noqa: E401
    results["env"]["versions"] = {"fastapi": fastapi.__version__, "starlette": starlette.__version__, "uvicorn": uvicorn.__version__}
    for key in a.only.split(","):
        print(f"== {key}", flush=True)
        results[key] = s7_recipe_load(a.src) if key == "S7" else SCEN[key](raw, a.src)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print("wrote", out.relative_to(REPO))


if __name__ == "__main__":
    main()
