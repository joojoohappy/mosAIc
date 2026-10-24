"""Abuse and cost protection for POST /api/generate.

Every limit is an environment variable with a deliberately small default, so a
fresh deployment cannot run up a large bill before anyone has looked at it.

    MOSAIC_RATE_PER_MINUTE   per visitor, per minute            default 3
    MOSAIC_DAILY_PER_CLIENT  per visitor, per UTC day            default 10
    MOSAIC_DAILY_GLOBAL      paid model calls, all visitors/day  default 50
    MOSAIC_MAX_CONCURRENT    model calls running at once         default 2

"Visitor" is the client IP, taken only from sources a client cannot forge
(see client_id). X-Forwarded-For is never trusted: anyone can send one.
Per-visitor and concurrency limits are kept in memory, so on a multi-instance
host each instance enforces them separately. The global daily budget is the
real cost guard: it is stored in the results store (local disk or Vercel Blob)
and is shared by every instance. Under heavy parallel load it can overshoot by
at most MOSAIC_MAX_CONCURRENT per instance. Set a hard spending cap with the
model provider as well.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def settings() -> dict:
    return {
        "rate_per_minute": _env_int("MOSAIC_RATE_PER_MINUTE", 3),
        "daily_per_client": _env_int("MOSAIC_DAILY_PER_CLIENT", 10),
        "daily_global": _env_int("MOSAIC_DAILY_GLOBAL", 50),
        "max_concurrent": _env_int("MOSAIC_MAX_CONCURRENT", 2),
    }


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def client_id(headers, peer: str | None) -> str:
    """Who is asking, for per-visitor limits. Never from X-Forwarded-For.

    1. x-mosaic-client-ip, but only with the matching MOSAIC_PROXY_SECRET: the
       website (apps/web/proxy.ts) sets it from the platform's own header.
    2. x-real-ip, only on Vercel (whose edge overwrites it) or when
       MOSAIC_TRUST_X_REAL_IP=1 behind your own reverse proxy.
    3. The socket peer. Behind an untrusted proxy every visitor then shares one
       bucket: stricter than intended, never looser.
    """
    secret = os.environ.get("MOSAIC_PROXY_SECRET", "")
    if secret:
        given = headers.get("x-mosaic-proxy-secret", "")
        ip = headers.get("x-mosaic-client-ip", "").strip()
        if ip and hmac.compare_digest(given.encode(), secret.encode()):
            return "ip:" + ip[:64]
    if os.environ.get("VERCEL") or os.environ.get("MOSAIC_TRUST_X_REAL_IP") == "1":
        real = headers.get("x-real-ip", "").strip()
        if real:
            return "ip:" + real[:64]
    return "peer:" + (peer or "unknown")


def fingerprint(recipe_id: str, image: bytes) -> str:
    return hashlib.sha256(recipe_id.encode() + b"\0" + image).hexdigest()


class Limiter:
    """In-memory per-visitor windows, duplicate detection and a concurrency gate."""

    DEDUPE_SECONDS = 600

    def __init__(self):
        self._lock = threading.Lock()
        self._minute: dict[str, deque] = defaultdict(deque)
        self._daily: dict[tuple[str, str], int] = defaultdict(int)
        self._recent: dict[str, tuple[str, float]] = {}
        self._running = 0

    def reset(self) -> None:
        with self._lock:
            self._minute.clear()
            self._daily.clear()
            self._recent.clear()
            self._running = 0

    # Same recipe + same photo within 10 minutes -> the earlier result. A double
    # click, a refresh mid-generation, or a resubmit never pays twice.
    def recent_result(self, key: str) -> str | None:
        with self._lock:
            hit = self._recent.get(key)
            if hit and time.monotonic() - hit[1] < self.DEDUPE_SECONDS:
                return hit[0]
            return None

    def remember(self, key: str, result_id: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._recent = {k: v for k, v in self._recent.items()
                            if now - v[1] < self.DEDUPE_SECONDS}
            self._recent[key] = (result_id, now)

    def admit(self, client: str) -> str | None:
        """Count one request for this visitor. Returns an error code or None."""
        cfg = settings()
        now = time.monotonic()
        with self._lock:
            window = self._minute[client]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= cfg["rate_per_minute"]:
                return "rate_limited"
            day = today()
            if len(self._daily) > 10_000:  # drop earlier days' counters
                self._daily = defaultdict(int, {k: v for k, v in self._daily.items()
                                                if k[1] == day})
            if len(self._minute) > 10_000:
                self._minute = defaultdict(deque, {k: w for k, w in self._minute.items()
                                                   if w and now - w[-1] <= 60})
                window = self._minute[client]
            day_key = (client, day)
            if self._daily[day_key] >= cfg["daily_per_client"]:
                return "daily_limit_reached"
            window.append(now)
            self._daily[day_key] += 1
            return None

    def acquire(self) -> bool:
        with self._lock:
            if self._running >= settings()["max_concurrent"]:
                return False
            self._running += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._running = max(0, self._running - 1)


class DailyBudget:
    """Shared count of paid model calls per UTC day, kept in a store."""

    def __init__(self, store_factory):
        self._store_factory = store_factory
        self._lock = threading.Lock()

    def _read(self, store, name: str) -> dict:
        raw = store.get(name)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    def reserve(self) -> bool:
        """Take one unit of today's budget before calling the provider."""
        limit = settings()["daily_global"]
        name = f"usage-{today()}.json"
        with self._lock:
            store = self._store_factory()
            data = self._read(store, name)
            if data.get("attempts", 0) >= limit:
                return False
            data["attempts"] = data.get("attempts", 0) + 1
            store.put(name, json.dumps(data).encode())
            return True

    def record(self, outcome: str) -> None:
        """outcome: 'live' (billable success) or 'failed'."""
        name = f"usage-{today()}.json"
        with self._lock:
            store = self._store_factory()
            data = self._read(store, name)
            data[outcome] = data.get(outcome, 0) + 1
            store.put(name, json.dumps(data).encode())

    def usage(self) -> dict:
        return self._read(self._store_factory(), f"usage-{today()}.json")
