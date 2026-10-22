"""Abuse and cost protection for POST /api/generate.

Every limit is an environment variable with a deliberately small default, so a
fresh deployment cannot run up a large bill before anyone has looked at it.

    MOSAIC_RATE_PER_MINUTE   per visitor, per minute            default 3
    MOSAIC_DAILY_PER_CLIENT  per visitor, per UTC day            default 10
    MOSAIC_DAILY_GLOBAL      paid model calls, all visitors/day  default 50
    MOSAIC_MAX_CONCURRENT    model calls running at once         default 2

"Visitor" is the client IP (first X-Forwarded-For hop when behind a proxy).
Per-visitor and concurrency limits are kept in memory, so on a multi-instance
host each instance enforces them separately. The global daily budget is the
real cost guard: it is stored in the results store (local disk or Vercel Blob)
and is shared by every instance. Under heavy parallel load it can overshoot by
at most MOSAIC_MAX_CONCURRENT per instance. Set a hard spending cap with the
model provider as well.
"""

from __future__ import annotations

import hashlib
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


def client_id(headers, fallback: str | None) -> str:
    forwarded = headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return first or fallback or "unknown"


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
            day_key = (client, today())
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
