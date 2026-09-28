"""Recipe lookup and the public projection.

Split from generation.py because these two answer different questions: this file
owns "what is a recipe and what may a client see", generation.py owns "how is a
result produced".
"""

from __future__ import annotations

import json
from pathlib import Path

RECIPES_FILE = Path(__file__).resolve().parent.parent / "data" / "recipes.json"

# An ALLOWLIST, not a "drop the prompt" denylist: a private field added to
# recipes.json later stays private by default instead of leaking on the next deploy.
PUBLIC_FIELDS = (
    "id", "title", "summary", "sourcePostUrl", "creatorName",
    "creatorInstagramUrl", "previewImageUrl", "inputNote", "tryReady",
)


def load_recipes() -> list[dict]:
    return json.loads(RECIPES_FILE.read_text(encoding="utf-8"))


def get_recipe(recipe_id: str) -> dict | None:
    return next((r for r in load_recipes() if r["id"] == recipe_id), None)


def public_recipe(recipe: dict) -> dict:
    """What a client is allowed to see. Never includes prompt text -- the whole
    point of recipeId-in-prompt-out is that the prompt stays server-side."""
    return {k: recipe.get(k) for k in PUBLIC_FIELDS}
