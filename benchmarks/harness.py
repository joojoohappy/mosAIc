"""Shared plumbing for the MOSAIC benchmarks.

- Backend: runs the real FastAPI app (uvicorn) from a throwaway copy of
  apps/backend, so benchmarks never touch the repo's storage/ or recipes.json.
- FakeProvider: the local Gemini stand-in from fake_gemini.py.
- ProcSampler: CPU and RSS of the uvicorn process tree, read from /proc.
- closed_loop(): a fixed number of requests from N concurrent workers, with
  per-request latency recorded.
- summarize(): p50/p95/p99 etc. from raw samples.

Linux only (/proc). Python stdlib + httpx (already in requirements-dev.txt).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = ROOT / "apps" / "backend"
PYTHON = BACKEND_SRC / ".venv" / "bin" / "python"
RESULTS = Path(__file__).resolve().parent / "results"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_gemini  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def environment() -> dict:
    """What the numbers were measured on. Saved next to every raw result."""
    def cmd(*args):
        try:
            return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001
            return None
    cpu = None
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mem_kb = None
    try:
        mem_kb = int(Path("/proc/meminfo").read_text().split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": "ephemeral cloud sandbox (shared, not dedicated hardware)",
        "os": platform.platform(),
        "cpu": cpu,
        "logicalCpus": os.cpu_count(),
        "memoryGiB": round(mem_kb / 1024 / 1024, 1) if mem_kb else None,
        "python": cmd(str(PYTHON), "--version"),
        "gitCommit": cmd("git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"),
        "backendSource": os.environ.get("MOSAIC_BENCH_SRC") or str(BACKEND_SRC),
    }


class FakeProvider:
    def __init__(self):
        self.server = fake_gemini.serve(free_port())
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.endpoint = self.base + "/v1beta/interactions"

    def set(self, mode: str = "ok", delay: float = 0.0) -> None:
        httpx.post(self.base + "/__mode", json={"mode": mode, "delay": delay})

    def calls(self) -> int:
        return httpx.get(self.base + "/__stats").json()["calls"]

    def reset(self) -> None:
        httpx.post(self.base + "/__reset")

    def close(self) -> None:
        self.server.shutdown()


class Backend:
    """uvicorn serving a temp copy of apps/backend (or MOSAIC_BENCH_SRC)."""

    def __init__(self, env: dict | None = None, workers: int = 1, ready: bool = True):
        src = Path(os.environ.get("MOSAIC_BENCH_SRC") or BACKEND_SRC)
        self.tmp = Path(tempfile.mkdtemp(prefix="mosaic-bench-"))
        for d in ("app", "data", "storage"):
            shutil.copytree(src / d, self.tmp / d,
                            ignore=shutil.ignore_patterns("results", "meta", "__pycache__"))
        recipes_path = self.tmp / "data" / "recipes.json"
        recipes = json.loads(recipes_path.read_text(encoding="utf-8"))
        for r in recipes:
            # Every shipped seed is tryReady=false; benchmarks need the generate path.
            r["tryReady"] = ready
        recipes_path.write_text(json.dumps(recipes, ensure_ascii=False), encoding="utf-8")

        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        full_env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("MOSAIC_", "GEMINI_", "BLOB_", "VERCEL"))}
        full_env.update({"GEMINI_API_KEY": "", "PYTHONUNBUFFERED": "1"})
        full_env.update(env or {})
        self.env, self.workers = full_env, workers
        self.log = open(self.tmp / "server.log", "a")
        self._spawn()

    def _spawn(self) -> None:
        args = [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                "--port", str(self.port), "--no-proxy-headers", "--log-level", "warning",
                "--no-access-log"]
        if self.workers > 1:
            args += ["--workers", str(self.workers)]
        self.proc = subprocess.Popen(args, cwd=self.tmp, env=self.env,
                                     stdout=self.log, stderr=subprocess.STDOUT)
        self.started = time.monotonic()
        self.startup_seconds = self.wait_healthy()

    def restart(self, hard: bool = False) -> float:
        """Stop the server (SIGTERM, or SIGKILL if hard) and start it again on the
        same storage. Returns seconds until /api/health answered again."""
        (self.proc.kill if hard else self.proc.terminate)()
        self.proc.wait(10)
        self._spawn()
        return self.startup_seconds

    def wait_healthy(self, timeout: float = 30) -> float:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if httpx.get(self.url + "/api/health", timeout=1).status_code == 200:
                    return time.monotonic() - self.started
            except httpx.HTTPError:
                pass
            if self.proc.poll() is not None:
                raise RuntimeError("backend exited:\n" + (self.tmp / "server.log").read_text())
            time.sleep(0.05)
        raise RuntimeError("backend did not become healthy")

    def server_log(self) -> str:
        self.log.flush()
        return (self.tmp / "server.log").read_text()

    def usage_file(self) -> dict:
        files = list((self.tmp / "storage" / "meta").glob("usage-*.json"))
        return json.loads(files[0].read_text()) if files else {}

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()


class ProcSampler:
    """Samples CPU seconds and RSS of a process and its children every `interval`."""

    def __init__(self, pid: int, interval: float = 0.1):
        self.pid, self.interval = pid, interval
        self.rss_peak_mb = 0.0
        self.rss_samples: list[float] = []
        self._stop = threading.Event()
        self._tick = os.sysconf("SC_CLK_TCK")

    def _tree(self) -> list[int]:
        pids, todo = [], [self.pid]
        while todo:
            p = todo.pop()
            pids.append(p)
            try:
                for t in Path(f"/proc/{p}/task").iterdir():
                    kids = (t / "children").read_text().split()
                    todo.extend(int(k) for k in kids)
            except OSError:
                pass
        return pids

    def _read(self) -> tuple[float, float]:
        cpu, rss = 0.0, 0.0
        for p in self._tree():
            try:
                fields = Path(f"/proc/{p}/stat").read_text().rsplit(")", 1)[1].split()
                cpu += (int(fields[11]) + int(fields[12])) / self._tick
                for line in Path(f"/proc/{p}/status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        rss += int(line.split()[1]) / 1024
            except (OSError, IndexError, ValueError):
                pass
        return cpu, rss

    def _loop(self):
        while not self._stop.is_set():
            _, rss = self._read()
            self.rss_samples.append(rss)
            self.rss_peak_mb = max(self.rss_peak_mb, rss)
            time.sleep(self.interval)

    def __enter__(self):
        self.cpu0, rss = self._read()
        self.rss_start_mb = rss
        self.t0 = time.monotonic()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        cpu1, rss = self._read()
        self.wall = time.monotonic() - self.t0
        self.cpu_seconds = cpu1 - self.cpu0
        self.cpu_util = self.cpu_seconds / self.wall if self.wall else 0.0  # 1.0 = one core
        self.rss_end_mb = rss


async def closed_loop(send, total: int, concurrency: int) -> tuple[list[dict], float]:
    """`total` requests from `concurrency` workers that each send back-to-back.

    `send(client, i)` returns (status_code, extra_dict). Returns per-request
    samples and the wall time of the whole batch.
    """
    samples: list[dict] = []
    counter = iter(range(total))
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=120) as client:
        async def worker():
            for i in counter:
                t0 = time.perf_counter()
                try:
                    status, extra = await send(client, i)
                except httpx.HTTPError as err:
                    status, extra = 0, {"error": type(err).__name__}
                samples.append({"i": i, "latency_ms": (time.perf_counter() - t0) * 1000,
                                "status": status, **(extra or {})})
        t0 = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(concurrency)))
        wall = time.perf_counter() - t0
    return samples, wall


def percentile(sorted_vals: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (numpy's default)."""
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def summarize(samples: list[dict], wall: float) -> dict:
    lat = sorted(s["latency_ms"] for s in samples)
    statuses: dict[str, int] = {}
    for s in samples:
        statuses[str(s["status"])] = statuses.get(str(s["status"]), 0) + 1
    return {
        "n": len(samples),
        "p50_ms": round(percentile(lat, 0.50), 2),
        "p95_ms": round(percentile(lat, 0.95), 2),
        "p99_ms": round(percentile(lat, 0.99), 2),
        "mean_ms": round(sum(lat) / len(lat), 2) if lat else None,
        "max_ms": round(lat[-1], 2) if lat else None,
        "throughput_rps": round(len(samples) / wall, 1) if wall else None,
        "statuses": statuses,
    }


def jpeg(width: int, height: int, quality: int = 90) -> bytes:
    """A deterministic photo-like JPEG (gradient + noise pattern), so Pillow has
    real work to do and every size is reproducible."""
    from PIL import Image
    img = Image.radial_gradient("L").resize((width, height)).convert("RGB")
    noise = Image.effect_noise((width, height), 40).convert("RGB")
    img = Image.blend(img, noise, 0.3)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def save(name: str, payload: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path
