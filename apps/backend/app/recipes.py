"""Recipe lookup and the public projection.

Split from generation.py because these two answer different questions: this file
owns "what is a recipe and what may a client see", generation.py owns "how is a
result produced".
"""

from __future__ import annotations

import json
from pathlib import Path

RECIPES_FILE = Path(__file__).resolve().parent.parent / "data" / "recipes.json"

# An ALLOWLIST, not a "drop the private bits" denylist: a field added to
# recipes.json later stays private by default instead of leaking on the next deploy.
PUBLIC_FIELDS = (
    "id", "title", "summary", "category", "tags", "sourcePostUrl", "creatorName",
    "creatorInstagramUrl", "previewBeforeUrl", "previewImageUrl", "inputNote", "aspectRatio",
    "promptVisibility", "tryReady",
)


def load_recipes() -> list[dict]:
    return json.loads(RECIPES_FILE.read_text(encoding="utf-8"))


def get_recipe(recipe_id: str) -> dict | None:
    return next((r for r in load_recipes() if r["id"] == recipe_id), None)


def public_recipe(recipe: dict) -> dict:
    """What a client is allowed to see.

    The prompt text is included only when the creator shared it publicly
    (promptVisibility == "public"). Anything else -- "hidden", a typo, a missing
    field -- keeps it server-side. Either way the client never *sends* a prompt:
    generation looks it up by recipeId, so showing it is read-only.
    """
    projection = {k: recipe.get(k) for k in PUBLIC_FIELDS}
    tags = recipe.get("tags")
    projection["tags"] = [t for t in tags if isinstance(t, str)] if isinstance(tags, list) else []
    public = recipe.get("promptVisibility") == "public"
    projection["promptVisibility"] = "public" if public else "hidden"
    projection["prompt"] = recipe.get("prompt") if public else None
    return projection
