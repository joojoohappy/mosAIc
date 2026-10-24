"""Pre-generate the fallback ("cached") result for one recipe.

    cd apps/backend && .venv/bin/python -m scripts.pregen seed-01 ./test-photo.jpg

It calls the same _call_provider the live path uses, so one successful run proves
the provider works, produces the cached asset, and records its provenance. Needs
GEMINI_API_KEY in apps/backend/.env. Use a photo you are allowed to publish: its
file name is quoted in every cached result's disclosure note.
"""

import json
import sys
import time
from pathlib import Path

from app import provider
from app.generation import API_KEY, FALLBACK_DIR, _call_provider, _is_image, _now
from app.recipes import get_recipe

if len(sys.argv) != 3:
    sys.exit(__doc__)
if not API_KEY:
    sys.exit("GEMINI_API_KEY is not set -- copy apps/backend/.env.example to .env first")

recipe_id, photo = sys.argv[1], Path(sys.argv[2])
recipe = get_recipe(recipe_id)
if recipe is None:
    sys.exit(f"unknown recipe: {recipe_id}")

started = time.monotonic()
img = _call_provider(recipe, photo.read_bytes())
duration = round(time.monotonic() - started, 1)

# If the provider answered with text -- a safety refusal, or it read the prompt as a
# question -- find out here, not in front of an audience.
ext = _is_image(img)
if ext is None:
    sys.exit(f"provider returned {len(img)} bytes that are not an image — inspect before retrying")

FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
(FALLBACK_DIR / f"{recipe_id}.{ext}").write_bytes(img)
(FALLBACK_DIR / f"{recipe_id}.json").write_text(
    json.dumps(
        {
            "image": f"{recipe_id}.{ext}",
            "provider": provider.NAME,
            "model": provider.model(),
            "generatedAt": _now(),
            "inputPhoto": photo.name,
            "durationSec": duration,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"ok — {recipe_id} fallback written in {duration}s.")
