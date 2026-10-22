"""Where generated results live.

Two interchangeable stores with the same tiny interface (put / get by name):

    LocalStore  files under storage/results/ -- the default for local dev and Docker
    BlobStore   Vercel Blob -- used automatically when a Blob store is connected
                (BLOB_READ_WRITE_TOKEN, or BLOB_STORE_ID on Vercel)

Vercel functions do not keep files between requests, so on Vercel a result
written to local disk would vanish and its share link would 404. Results are
always served back through the API (/static/results/<name>), so the browser
never needs to know which store is in use and a private Blob store works.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

CONTENT_TYPES = {
    "json": "application/json",
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}


class Store(Protocol):
    def put(self, name: str, data: bytes) -> None: ...
    def get(self, name: str) -> bytes | None: ...


def content_type(name: str) -> str:
    return CONTENT_TYPES.get(name.rsplit(".", 1)[-1], "application/octet-stream")


class LocalStore:
    def __init__(self, root: Path):
        self.root = root

    def put(self, name: str, data: bytes) -> None:
        # tmp + replace: a reader that arrives mid-write sees the old file or
        # nothing, never half a JSON document.
        self.root.mkdir(parents=True, exist_ok=True)
        final = self.root / name
        tmp = final.with_name(final.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, final)

    def get(self, name: str) -> bytes | None:
        try:
            return (self.root / name).read_bytes()
        except OSError:
            return None


class BlobStore:
    """Vercel Blob via the official `vercel` SDK (sync API)."""

    def __init__(self, client, access: str = "private", prefix: str = "results/"):
        self.client = client
        self.access = access
        self.prefix = prefix

    def put(self, name: str, data: bytes) -> None:
        self.client.put_blob(
            self.prefix + name,
            data,
            access=self.access,
            content_type=content_type(name),
            add_random_suffix=False,
            allow_overwrite=True,
        )

    def get(self, name: str) -> bytes | None:
        try:
            return self.client.get_blob(self.prefix + name, access=self.access).body
        except Exception as err:  # noqa: BLE001 - missing or unreachable reads as absent
            if type(err).__name__ != "BlobNotFoundError":
                print(f"[storage] blob read failed for {name}: {type(err).__name__}: {err}")
            return None


def blob_configured() -> bool:
    return bool(
        os.environ.get("BLOB_READ_WRITE_TOKEN")
        or os.environ.get("VERCEL_BLOB_READ_WRITE_TOKEN")
        or os.environ.get("BLOB_STORE_ID")
    )


def results_store(local_root: Path, kind: str = "results") -> Store:
    """kind: "results" (images + result JSON) or "meta" (usage counters)."""
    if blob_configured():
        from vercel.blob import sync as blob  # imported only when a store is connected

        access = "public" if os.environ.get("BLOB_ACCESS") == "public" else "private"
        return BlobStore(blob, access=access, prefix=f"{kind}/")
    if os.environ.get("VERCEL"):
        # Read-only deploy bundle: /tmp is the only writable place. Data lives
        # only as long as this instance -- connect a Blob store to keep it.
        return LocalStore(Path("/tmp/mosaic") / kind)
    return LocalStore(local_root)
