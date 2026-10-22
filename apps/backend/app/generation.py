"""MOSAIC generation pipeline.

Framework-free on purpose: no FastAPI imports, so it can be tested on its own.

Three result modes, and one of them is ALWAYS declared:

    live   - provider returned real image bytes, generated from the user's photo
    cached - a pre-generated result from OUR test photo, with provenance
    mock   - nothing has been generated for this recipe yet

Three invariants. Break any one and "the server does not lie" is gone:

 1. _call_provider() returns bytes and NEVER touches the filesystem. Every write
    happens once, in _write_result, after mode is decided. A zombie thread that
    finishes after the timeout can therefore never overwrite a cached result.
 2. mode == "live" means we really hold an image. Provider output goes through the
    same magic-byte check as uploads; a 200 carrying text is a failure.
 3. The user's photo is never retained. Bytes -> provider -> dropped. Nothing under
    storage/ is user input.
    Caveat, stated rather than glossed: Starlette spools a large multipart upload to
    a temp file before we see it, and deletes it when the request ends. We never
    copy it anywhere.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from . import provider
from .limits import DailyBudget
from .storage import blob_configured, results_store

# Paths resolve from this file, never from cwd -- uvicorn and pytest run from
# different directories.
ROOT = Path(__file__).resolve().parent.parent   # apps/backend/
STORAGE = ROOT / "storage"
FALLBACK_DIR = STORAGE / "fallback"
RESULTS_DIR = STORAGE / "results"

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000  # decompression-bomb guard: ~ 8000 x 5000
RESULT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SIDECAR_REQUIRED = ("image", "provider", "model", "generatedAt", "inputPhoto")


# apps/backend/.env (gitignored) holds the key; see .env.example. Loaded here
# rather than in main.py so pregen.py gets it too.
load_dotenv(ROOT / ".env")
API_KEY = os.environ.get("GEMINI_API_KEY")
log = logging.getLogger("mosaic.generation")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_image(b: bytes) -> str | None:
    """Magic bytes, not Content-Type. The client fills in Content-Type; it lies.

    Shared by upload validation and provider-output validation on purpose -- one
    definition of "this is an image" for both trust boundaries.
    """
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return None



def validate_upload(data: bytes) -> str | None:
    """None if `data` is a real JPEG/PNG/WebP photo, else an API error code.

    Magic bytes first (cheap, and the client's Content-Type is not trusted),
    then a real decode so a renamed or truncated file is caught here rather
    than by the paid model call.
    """
    kind = _is_image(data)
    if kind is None:
        return "unsupported_type"
    try:
        from PIL import Image  # Pillow

        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > MAX_PIXELS:
                return "invalid_image"
            if kind == "png":
                # verify() checks every chunk CRC, which catches truncation.
                img.verify()
            else:
                # For JPEG, verify() only parses headers: a photo cut off at 1%
                # passed. Decoding walks the whole compressed stream. draft()
                # lets libjpeg decode at 1/8 scale, which still reads every byte
                # but costs about half of a full decode (benchmarks/
                # compare_validation.py). WebP has no draft mode: full decode.
                if kind == "jpg":
                    img.draft("RGB", (max(1, img.width // 8), max(1, img.height // 8)))
                img.load()
    except Exception:  # noqa: BLE001 - any decode failure means "not a usable photo"
        return "invalid_image"
    return None


class QuotaExceeded(Exception):
    """Today's global budget of paid model calls is used up."""


def _meta_store():
    return results_store(STORAGE / "meta", kind="meta")


budget = DailyBudget(_meta_store)


def _reason_code(err: Exception) -> str:
    """Public, non-sensitive summary of a provider failure. Details go to the log."""
    import socket
    import urllib.error

    timeouts = (TimeoutError, socket.timeout)
    if isinstance(err, timeouts) or (
        isinstance(err, urllib.error.URLError) and isinstance(err.reason, timeouts)
    ):
        return "provider_timeout"
    if isinstance(err, ValueError):
        return "provider_no_image"
    return "provider_error"


def _read_sidecar(recipe_id: str) -> dict | None:
    """A sidecar counts only if it parses, has every provenance field, and its image
    exists inside fallback/ AND is really an image. Anything else degrades to mock --
    never raises."""
    path = FALLBACK_DIR / f"{recipe_id}.json"
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        if any(not meta.get(k) for k in SIDECAR_REQUIRED):
            return None
        img = (FALLBACK_DIR / meta["image"]).resolve()
        if img.parent != FALLBACK_DIR.resolve():
            return None
        # Read the bytes rather than stat the path: a truncated or half-written
        # fallback would otherwise be served as a "cached" result with a
        # provenance note claiming a real generation produced it.
        # Missing file raises OSError -> caught below -> degrades to mock.
        if _is_image(img.read_bytes()) is None:
            return None
        return meta
    except (OSError, ValueError, TypeError):
        return None


def _call_provider(recipe: dict, image_bytes: bytes) -> bytes:
    """Recipe prompt + user photo -> image bytes. Returns bytes only; writes nothing.

    The provider call itself lives in provider.py (hard deadline, zero retries,
    no filesystem access). Patched out in tests.
    """
    return provider.generate(
        API_KEY or "",
        recipe["prompt"],
        image_bytes,
        _is_image(image_bytes) or "png",
        recipe.get("aspectRatio"),
    )


def _load_fallback(recipe_id: str) -> tuple[bytes | None, str, dict | None]:
    meta = _read_sidecar(recipe_id)
    if meta is None:
        return None, "mock", None
    return (FALLBACK_DIR / meta["image"]).read_bytes(), "cached", meta


def _source_note(mode: str, meta: dict | None) -> str:
    if mode == "live":
        return "即時生成：這張圖由你這次上傳的照片產生。"
    if mode == "cached" and meta:
        return (
            f"預備結果，不是由你這次上傳的照片生成。這張圖是 {meta['generatedAt']} "
            f"以團隊測試照片（{meta['inputPhoto']}）透過 {meta['provider']} / "
            f"{meta['model']} 產生。"
        )
    return "示意用途：這份 recipe 目前還沒有實際生成過任何結果。"


def _write_result(recipe: dict, img: bytes | None, mode: str, meta: dict | None,
                  reason: str | None) -> dict:
    """The only place anything is written. Image first, then JSON, because the
    frontend GETs the result the instant it has the ID and must never read a URL
    pointing at an image that isn't stored yet."""
    result_id = uuid.uuid4().hex
    store = results_store(RESULTS_DIR)

    image_url = None
    if img is not None:
        name = f"{result_id}.{_is_image(img) or 'png'}"
        store.put(name, img)
        image_url = f"/static/results/{name}"

    result = {
        "resultId": result_id,
        "recipeId": recipe["id"],
        "mode": mode,
        "sourceNote": _source_note(mode, meta),
        "imageUrl": image_url,
        "fallbackReason": reason,
        "recipeTitle": recipe["title"],
        "creatorName": recipe["creatorName"],
        "sourcePostUrl": recipe["sourcePostUrl"],
        "creatorInstagramUrl": recipe["creatorInstagramUrl"],
        "createdAt": _now(),
    }
    store.put(f"{result_id}.json", json.dumps(result, ensure_ascii=False).encode("utf-8"))
    return result


def live_blocker() -> str | None:
    """Why paid generation is switched off right now, or None if it is on.

    On Vercel without a Blob store, results and the daily budget would live in
    one instance's /tmp: links would break and the budget would reset on every
    cold start. Better to stay in fallback mode than to pay for that.
    """
    if not API_KEY:
        return "no_api_key"
    if os.environ.get("VERCEL") and not blob_configured():
        return "no_shared_storage"
    return None


def run_generation(recipe: dict, image_bytes: bytes) -> dict:
    """recipe + user photo -> a labelled result.

    Never raises for provider failure (it falls back to cached/mock). Raises
    QuotaExceeded, before any paid call, when today's budget is used up.
    """
    img: bytes | None = None
    mode, meta = "mock", None
    reason = live_blocker()
    if reason is None:
        if not budget.reserve():
            raise QuotaExceeded
        try:
            img = _call_provider(recipe, image_bytes)
            if _is_image(img) is None:
                raise ValueError("provider returned bytes that are not an image")
            mode = "live"
            budget.record("live")
        except Exception as err:  # noqa: BLE001 - every provider failure falls back
            img, reason = None, _reason_code(err)
            budget.record("failed")
            log.warning("provider failed recipe=%s reason=%s detail=%s",
                        recipe["id"], reason, f"{type(err).__name__}: {err}"[:300])

    if img is None:
        img, mode, meta = _load_fallback(recipe["id"])

    return _write_result(recipe, img, mode, meta, reason)


def retention_days() -> int:
    try:
        return max(1, int(os.environ.get("MOSAIC_RESULT_RETENTION_DAYS", 30)))
    except ValueError:
        return 30


def _expired(result: dict) -> bool:
    try:
        created = datetime.strptime(result["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
    except (KeyError, TypeError, ValueError):
        return False
    age = datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)
    return age.days >= retention_days()


def load_result(result_id: str) -> dict | None:
    """A stored result, or None if unknown or older than the retention period.

    The id is validated before it ever reaches a path or blob name --
    "../../etc/passwd" is a 404, not a file read.
    """
    if not RESULT_ID_RE.match(result_id):
        return None
    raw = results_store(RESULTS_DIR).get(f"{result_id}.json")
    try:
        result = json.loads(raw) if raw is not None else None
    except ValueError:
        return None
    if not isinstance(result, dict) or _expired(result):
        return None
    return result


RESULT_FILE_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|webp)$")


def load_result_image(name: str) -> bytes | None:
    """Bytes of a stored result image, or None. Only result image names pass."""
    if not RESULT_FILE_RE.match(name) or load_result(name.split(".")[0]) is None:
        return None
    return results_store(RESULTS_DIR).get(name)
