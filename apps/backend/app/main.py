"""MOSAIC backend — five routes and a static mount. That is the whole HTTP layer.

Run:  uvicorn app.main:app --app-dir backend --port 8000   (no --reload for a demo)

No CORS middleware, deliberately. The website's next.config.js proxies /api/* and
/static/* here, so the browser only ever talks to localhost:3000.

Routes are `def`, not `async def`. Starlette runs sync routes in a threadpool, so a
blocking 40-second provider SDK call cannot freeze the event loop — /api/health stays
responsive while a generation is in flight, which is exactly the Checkpoint 1 test.
"""

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .generation import MAX_BYTES, STORAGE, _is_image, load_result, run_generation
from .recipes import get_recipe, load_recipes, public_recipe

app = FastAPI(title="MOSAIC backend")

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
def health():
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
def generate(
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
    # unbounded upload into memory.
    data = image.file.read(MAX_BYTES + 1)
    if not data:
        return _err(400, "missing_image")
    if len(data) > MAX_BYTES:
        return _err(400, "too_large")
    if _is_image(data) is None:
        return _err(400, "unsupported_type")

    return {"resultId": run_generation(recipe, data)["resultId"]}


@app.get("/api/results/{result_id}")
def read_result(result_id: str):
    # load_result rejects anything that isn't 32 hex chars before touching a path.
    result = load_result(result_id)
    return result if result is not None else _err(404, "unknown_result")
