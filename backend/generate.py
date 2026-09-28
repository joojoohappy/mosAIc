"""MOSAIC generation pipeline.

Framework-free on purpose: no FastAPI imports, so this runs and is testable before
the Next.js app exists.

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

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Paths resolve from this file, never from cwd -- uvicorn and pytest run from
# different directories.
ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / "storage"
FALLBACK_DIR = STORAGE / "fallback"
RESULTS_DIR = STORAGE / "results"
RECIPES_FILE = ROOT.parent / "data" / "recipes.json"

MAX_BYTES = 8 * 1024 * 1024
RESULT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SIDECAR_REQUIRED = ("image", "provider", "model", "generatedAt", "inputPhoto")

# An ALLOWLIST, not a "drop the prompt" denylist: a private field added to
# recipes.json later stays private by default instead of leaking on the next deploy.
PUBLIC_FIELDS = (
    "id", "title", "summary", "sourcePostUrl", "creatorName",
    "creatorInstagramUrl", "previewImageUrl", "inputNote", "tryReady",
)

# backend/.env (gitignored) holds the key; see .env.example. Loaded here rather
# than in main.py so pregen.py and the tests get it too.
load_dotenv(ROOT / ".env")
API_KEY = os.environ.get("ANTHROPIC_API_KEY")


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


def load_recipes() -> list[dict]:
    return json.loads(RECIPES_FILE.read_text(encoding="utf-8"))


def get_recipe(recipe_id: str) -> dict | None:
    return next((r for r in load_recipes() if r["id"] == recipe_id), None)


def public_recipe(recipe: dict) -> dict:
    """What a client is allowed to see. Never includes prompt text -- the whole
    point of recipeId-in-prompt-out is that the prompt stays server-side."""
    return {k: recipe.get(k) for k in PUBLIC_FIELDS}


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


def _call_provider(prompt: str, image_bytes: bytes) -> bytes:
    """Prompt + user photo -> image bytes. Returns bytes only; writes nothing.

    NOT IMPLEMENTED -- no provider selected yet (CREATIVE-RECIPE.md:68).

    This is pre-Build-Day work, not day-of work: pregen.py is this function's CLI
    entry point, so running pregen before the event already requires it to exist.
    Fill it in by reading the provider's live docs for the exact model id, endpoint
    and request shape. Do not write the call from memory.

    Must honour: a hard deadline, zero retries, no filesystem access.
    Set the deadline from what pregen measured — the slowest seed's durationSec in
    storage/fallback/*.json, times 1.5, capped at 60s. A round number picked now
    would just be a guess about a provider nobody has called yet.
    """
    raise NotImplementedError("provider not selected yet -- see docstring")


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
    """The only place anything is written. Image first, then JSON via tmp+replace,
    because the frontend GETs the result the instant it has the ID and must never
    read half a JSON or a URL pointing at a file that isn't there yet."""
    result_id = uuid.uuid4().hex
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    image_url = None
    if img is not None:
        ext = _is_image(img) or "png"
        (RESULTS_DIR / f"{result_id}.{ext}").write_bytes(img)
        image_url = f"/static/results/{result_id}.{ext}"

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

    final = RESULTS_DIR / f"{result_id}.json"
    tmp = final.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, final)
    return result


def run_generation(recipe: dict, image_bytes: bytes) -> dict:
    """recipe + user photo -> a labelled result. Never raises for provider failure."""
    img: bytes | None = None
    mode, reason, meta = "mock", None, None

    if API_KEY:
        try:
            img = _call_provider(recipe["prompt"], image_bytes)
            if _is_image(img) is None:
                raise ValueError("provider returned bytes that are not an image")
            mode = "live"
        except Exception as err:  # noqa: BLE001 - every provider failure falls back
            img, reason = None, f"{type(err).__name__}: {err}"[:200]
    else:
        reason = "no_api_key"

    if img is None:
        img, mode, meta = _load_fallback(recipe["id"])
        print(f"[generate] {recipe['id']} -> {mode} ({reason})")

    return _write_result(recipe, img, mode, meta, reason)


def load_result(result_id: str) -> dict | None:
    # Validate before the id ever reaches a path join -- "../../etc/passwd" is a 404,
    # not a file read.
    if not RESULT_ID_RE.match(result_id):
        return None
    path = RESULTS_DIR / f"{result_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
