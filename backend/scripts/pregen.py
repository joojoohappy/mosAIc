"""Pre-generate the fallback layer. Run this BEFORE Build Day, not during it.

    cd backend && python -m scripts.pregen seed-01 ./test-photo.jpg

It calls the same _call_provider the live path uses, so one successful run does four
things at once: proves the provider works, produces the cached asset, records its
provenance, and fills the empty 實測 row in docs/build-day/SEED-RECIPES.md.

This is also why the live branch is pre-Build-Day work: you cannot run pregen without
_call_provider already written.
"""

import json
import sys
import time
from pathlib import Path

from app.generation import FALLBACK_DIR, _call_provider, _is_image, _now
from app.recipes import get_recipe

PROVIDER = "TODO: provider name"  # fill in when selected
MODEL = "TODO: exact model id"    # copy from the provider's live docs, not memory

if len(sys.argv) != 3:
    sys.exit(__doc__)

recipe_id, photo = sys.argv[1], Path(sys.argv[2])
recipe = get_recipe(recipe_id)
if recipe is None:
    sys.exit(f"unknown recipe: {recipe_id}")

started = time.monotonic()
img = _call_provider(recipe["prompt"], photo.read_bytes())
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
            "provider": PROVIDER,
            "model": MODEL,
            "generatedAt": _now(),
            "inputPhoto": photo.name,
            "durationSec": duration,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"ok — {recipe_id} fallback written in {duration}s. Record it in docs/build-day/SEED-RECIPES.md too.")
