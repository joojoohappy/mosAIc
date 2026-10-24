"""MOSAIC backend: the whole HTTP layer.

Run:  uvicorn app.main:app --app-dir apps/backend --port 8000

No CORS middleware, deliberately. The website proxies /api/* and /static/* here
(next.config.ts rewrites), so browsers only ever talk to the website's own
origin. Without CORS headers, other sites' pages cannot call this API from a
visitor's browser.

Routes are `def`, not `async def`. Starlette runs sync routes in a threadpool, so
a slow model call cannot freeze the event loop: /api/health stays responsive
while a generation is in flight.
"""

import logging
import time

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import generation
from .generation import (
    MAX_BYTES, STORAGE, QuotaExceeded, load_result, load_result_image,
    run_generation, validate_upload,
)
from .limits import Limiter, client_id, fingerprint
from .recipes import get_recipe, load_recipes, public_recipe
from .storage import content_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("mosaic.api")

# Multipart overhead on top of the largest allowed photo.
MAX_REQUEST_BYTES = MAX_BYTES + 512 * 1024


class BodySizeLimit:
    """Reject oversized request bodies before they are spooled to disk.

    Checks Content-Length up front and also counts streamed bytes, so a chunked
    upload without a length cannot slip past.
    """

    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > self.limit:
            return await _too_large(send)

        seen, started, rejected = 0, False, False

        async def limited_receive():
            nonlocal seen, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit:
                    # Answer now, then tell the app the client went away. Raising
                    # here instead would be caught by FastAPI's form parsing and
                    # turned into a generic 400 "error parsing the body", which the
                    # web client cannot map to too_large.
                    rejected = True
                    if not started:
                        await _too_large(send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            nonlocal started
            if rejected:
                return  # our 413 already went out; drop whatever the app sends
            started = started or message["type"] == "http.response.start"
            await send(message)

        await self.app(scope, limited_receive, guarded_send)


async def _too_large(send):
    body = b'{"error":"too_large"}'
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


app = FastAPI(title="MOSAIC backend", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(BodySizeLimit, limit=MAX_REQUEST_BYTES)
limiter = Limiter()

if generation.live_blocker() == "no_shared_storage":
    log.warning("GEMINI_API_KEY is set but no Blob store is connected on Vercel: "
                "live generation stays off (connect a Blob store to turn it on)")
if not any(r.get("tryReady") for r in load_recipes()):
    log.warning("no recipe has tryReady=true: POST /api/generate will return 403 "
                "recipe_not_ready for all of them (apps/backend/data/recipes.json)")


def _err(code: int, error: str) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=code)


@app.get("/api/health")
def health():
    # Lets the frontend say "backend is down" instead of a generic error, and
    # tell the user up front whether results will be live or a fallback.
    return {"ok": True, "liveGeneration": generation.live_blocker() is None}


@app.get("/api/recipes")
def list_recipes():
    # Public projection only (see recipes.public_recipe).
    return {"recipes": [public_recipe(r) for r in load_recipes()]}


@app.get("/api/recipes/{recipe_id}")
def read_recipe(recipe_id: str):
    recipe = get_recipe(recipe_id)
    return public_recipe(recipe) if recipe else _err(404, "unknown_recipe")


@app.post("/api/generate")
def generate(
    request: Request,
    # Both default to None so a missing field is our own 400, not FastAPI's 422.
    recipeId: str | None = Form(None),  # noqa: N803 - wire contract is camelCase
    image: UploadFile | None = File(None),
):
    if not recipeId:
        return _err(400, "missing_recipe_id")

    # recipeId in, prompt out. The client never supplies prompt text, or the API
    # key becomes a free image generator for anyone who opens devtools.
    recipe = get_recipe(recipeId)
    if recipe is None:
        return _err(404, "unknown_recipe")

    # An unverified recipe must not reach the provider.
    if not recipe.get("tryReady"):
        return _err(403, "recipe_not_ready")

    if image is None:
        return _err(400, "missing_image")

    # Read one byte past the limit: enough to know it's too large, without
    # pulling an unbounded upload into memory.
    data = image.file.read(MAX_BYTES + 1)
    if not data:
        return _err(400, "missing_image")
    if len(data) > MAX_BYTES:
        return _err(413, "too_large")
    problem = validate_upload(data)
    if problem:
        return _err(400, problem)

    # Same recipe + same photo within 10 minutes: hand back the earlier result.
    # (Identical requests that are still running are handled by limiter.lead.)
    key = fingerprint(recipe["id"], data)
    earlier = limiter.recent_result(key)
    if earlier:
        return {"resultId": earlier}

    who = client_id(request.headers, request.client.host if request.client else None)
    refused = limiter.admit(who)
    if refused:
        log.info("generate refused recipe=%s reason=%s", recipe["id"], refused)
        return _err(429, refused)

    # An identical request still in flight (a refresh or second click during
    # the 10-60 s model call): wait for it and hand back the same result.
    role = limiter.lead(key)
    if role == "waited":
        earlier = limiter.recent_result(key)
        if earlier:
            return {"resultId": earlier}
        # It ended without a result (busy, budget, error): answer this one on its own.
    if role != "lead":
        return _generate_once(recipe, data, key)
    try:
        return _generate_once(recipe, data, key)
    finally:
        limiter.done(key)


def _generate_once(recipe: dict, data: bytes, key: str):
    if not limiter.acquire():
        return _err(503, "server_busy")
    started = time.monotonic()
    try:
        result = run_generation(recipe, data)
    except QuotaExceeded:
        log.warning("generate refused recipe=%s reason=daily_budget_reached", recipe["id"])
        return _err(503, "daily_budget_reached")
    finally:
        limiter.release()
    limiter.remember(key, result["resultId"])
    log.info("generate recipe=%s mode=%s reason=%s seconds=%.1f", recipe["id"],
             result["mode"], result["fallbackReason"], time.monotonic() - started)
    return {"resultId": result["resultId"]}


@app.get("/api/results/{result_id}")
def read_result(result_id: str):
    # load_result rejects anything that isn't 32 hex chars before touching storage.
    result = load_result(result_id)
    return result if result is not None else _err(404, "unknown_result")


@app.get("/static/results/{name}")
def read_result_image(name: str):
    # Served from the results store (local disk or Vercel Blob); only
    # "<32 hex>.<png|jpg|webp>" names are accepted.
    data = load_result_image(name)
    if data is None:
        return _err(404, "unknown_result")
    # Unguessable and immutable; "private" keeps shared CDNs from caching it.
    return Response(data, media_type=content_type(name),
                    headers={"Cache-Control": "private, max-age=86400, immutable"})


# Creator preview images only. Fallback sidecars and anything else in storage/
# are never served.
app.mount("/static/seed", StaticFiles(directory=STORAGE / "seed", check_dir=False),
          name="seed")
