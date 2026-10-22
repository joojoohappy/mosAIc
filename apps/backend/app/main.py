"""MOSAIC backend — five routes and a static mount. That is the whole HTTP layer.

Run:  uvicorn app.main:app --app-dir backend --port 8000   (no --reload for a demo)

No CORS middleware, deliberately. The website's next.config.js proxies /api/* and
/static/* here, so the browser only ever talks to localhost:3000.

Read routes are `def`: Starlette runs them in its shared threadpool (40 threads by
default). Generation does NOT use that pool. A blocking provider call runs under its
own capacity limiter (MOSAIC_MAX_CONCURRENT_GENERATIONS), so slow generations queue
behind each other instead of starving /api/health, recipe pages and result pages.
Measured before this split: with 40 generations in flight, /api/health took ~4.8 s
(benchmarks/results/baseline.json, scenario S2).
"""

import json

import anyio
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .generation import (
    MAX_BYTES, MAX_CONCURRENT_GENERATIONS, STORAGE, _is_image, load_result, run_generation,
)
from .recipes import get_recipe, load_recipes, public_recipe

# Concurrent generations. Each one holds up to 8 MB of upload in memory and, once a
# provider exists, counts against its rate limit. Excess requests wait (the browser and
# the Next.js proxy both allow 75 s) rather than failing.
_generation_slots = anyio.CapacityLimiter(MAX_CONCURRENT_GENERATIONS)

# multipart framing + the recipeId field on top of the 8 MB image limit
MAX_REQUEST_BYTES = MAX_BYTES + 64 * 1024


class UploadSizeLimit:
    """Reject oversized POST /api/generate bodies before Starlette spools them to disk.

    Without this, the multipart parser reads the WHOLE body (measured: a 256 MB upload
    was fully received before the 400; benchmarks scenario S3) and only then does the
    route see the size. A declared Content-Length is rejected without reading a byte; a
    chunked body is cut off as soon as it crosses the limit. Both answer
    400 {"error": "too_large"}, the documented contract.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not (scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == "/api/generate"):
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
            await _send_too_large(send)
            return
        received, started, rejected = 0, False, False

        async def limited_receive():
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    # Answer now, then tell the app the client went away. Raising here
                    # would be caught by FastAPI's body parsing and turned into a
                    # generic 400 that the frontend cannot map to "too_large".
                    rejected = True
                    if not started:
                        await _send_too_large(send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            nonlocal started
            if rejected:
                return  # our 400 already went out; drop whatever the app tries to send
            started = started or message["type"] == "http.response.start"
            await send(message)

        await self.app(scope, limited_receive, guarded_send)


async def _send_too_large(send):
    body = json.dumps({"error": "too_large"}).encode()
    await send({"type": "http.response.start", "status": 400,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                            (b"connection", b"close")]})
    await send({"type": "http.response.body", "body": body})


app = FastAPI(title="MOSAIC backend")
app.add_middleware(UploadSizeLimit)

STORAGE.mkdir(parents=True, exist_ok=True)  # results/ and fallback/ are made on demand
app.mount("/static", StaticFiles(directory=STORAGE), name="static")

# tryReady defaults to false until a human establishes a basis for running a prompt.
# That is the honest default, but "every generate 403s" is a terrible thing to
# discover during a demo, so say it at startup rather than at 14:00.
if not any(r.get("tryReady") for r in load_recipes()):
    print("[recipes] WARNING: no recipe has tryReady=true — POST /api/generate will "
          "return 403 recipe_not_ready for all of them. Flip the ones you have "
          "verified in backend/data/recipes.json.")


def _err(code: int, error: str) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=code)


@app.get("/api/health")
async def health():
    # async + no I/O: answered on the event loop, so it never waits for a worker thread.
    # Two lines that tell Person 1 "backend is down" instead of a generic error.
    return {"ok": True}


@app.get("/api/recipes")
def list_recipes():
    # Public projection only. The client never receives prompt text.
    return {"recipes": [public_recipe(r) for r in load_recipes()]}


@app.get("/api/recipes/{recipe_id}")
def read_recipe(recipe_id: str):
    recipe = get_recipe(recipe_id)
    return public_recipe(recipe) if recipe else _err(404, "unknown_recipe")


@app.post("/api/generate")
async def generate(
    # Both default to None so a missing field is our own 400, not FastAPI's 422.
    # The documented contract says 400; the code has to actually return 400.
    recipeId: str | None = Form(None),  # noqa: N803 - wire contract is camelCase
    image: UploadFile | None = File(None),
):
    if not recipeId:
        return _err(400, "missing_recipe_id")

    # recipeId in, prompt out. The client never supplies prompt text, or the API key
    # becomes a free image generator for anyone who opens devtools.
    recipe = get_recipe(recipeId)
    if recipe is None:
        return _err(404, "unknown_recipe")

    # Checked before the upload is read: an unverified recipe must not reach the
    # provider, and there is no reason to pull 8MB off the wire to find that out.
    if not recipe.get("tryReady"):
        return _err(403, "recipe_not_ready")

    if image is None:
        return _err(400, "missing_image")

    # Read one byte past the limit: enough to know it's too large, without pulling an
    # unbounded upload into memory. (UploadSizeLimit has already capped the body.)
    data = await image.read(MAX_BYTES + 1)
    if not data:
        return _err(400, "missing_image")
    if len(data) > MAX_BYTES:
        return _err(400, "too_large")
    if _is_image(data) is None:
        return _err(400, "unsupported_type")

    # The blocking pipeline runs in a worker thread under its own limiter, not the
    # shared pool that serves health/recipes/results.
    result = await anyio.to_thread.run_sync(run_generation, recipe, data, limiter=_generation_slots)
    return {"resultId": result["resultId"]}


@app.get("/api/results/{result_id}")
def read_result(result_id: str):
    # load_result rejects anything that isn't 32 hex chars before touching a path.
    result = load_result(result_id)
    return result if result is not None else _err(404, "unknown_result")
