"""Launch the REAL MOSAIC FastAPI app from an isolated temp copy, with optional,
clearly-labelled test doubles. Used by every backend benchmark in this folder.

    python benchmarks/run_backend.py --port 8100
    python benchmarks/run_backend.py --port 8100 --ready seed-01 --provider sleep:2
    python benchmarks/run_backend.py --port 8100 --ready seed-01 --fallback-bytes 1500000

What is real:  app/main.py, app/generation.py, app/recipes.py, uvicorn, Starlette
               multipart parsing, disk writes, the thread pool.
What is fake:  --provider replaces generation._call_provider (which is still
               NotImplementedError in the repo) with a sleep that returns a 1x1 PNG.
               --fallback-bytes writes a synthetic "cached" asset + sidecar.
Nothing here measures an AI model. There is no AI model in the repository yet.

The repo's own data/recipes.json and storage/ are never touched.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "apps" / "backend"
PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--ready", action="append", default=[], help="recipe id to flip tryReady=true (copy only)")
    ap.add_argument("--provider", default=None, help="sleep:<seconds> | hang | error  (simulated provider)")
    ap.add_argument("--fallback-bytes", type=int, default=0, help="write a synthetic cached asset of N bytes for every ready recipe")
    ap.add_argument("--src", default=str(BACKEND), help="backend source dir to copy (lets before/after runs use different trees)")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="mosaic-bench-"))
    src = Path(args.src)
    shutil.copytree(src / "app", tmp / "app")
    shutil.copytree(src / "data", tmp / "data")
    recipes_path = tmp / "data" / "recipes.json"
    recipes = json.loads(recipes_path.read_text(encoding="utf-8"))
    for r in recipes:
        if r["id"] in args.ready:
            r["tryReady"] = True
    recipes_path.write_text(json.dumps(recipes, ensure_ascii=False), encoding="utf-8")

    if args.fallback_bytes:
        fb = tmp / "storage" / "fallback"
        fb.mkdir(parents=True, exist_ok=True)
        for rid in args.ready:
            # Valid PNG signature + padding: passes the magic-byte check, sized like a real poster.
            (fb / f"{rid}.png").write_bytes(PNG_1x1 + b"\0" * max(0, args.fallback_bytes - len(PNG_1x1)))
            (fb / f"{rid}.json").write_text(json.dumps({
                "image": f"{rid}.png", "provider": "SYNTHETIC-BENCHMARK", "model": "none",
                "generatedAt": "2026-10-23T00:00:00Z", "inputPhoto": "synthetic.png", "durationSec": 0,
            }), encoding="utf-8")

    sys.path.insert(0, str(tmp))
    os.chdir(tmp)
    from app import generation  # noqa: E402  (import after path setup)

    if args.provider:
        generation.API_KEY = "SIMULATED"  # forces the live branch; no key is ever sent anywhere
        kind, _, val = args.provider.partition(":")

        def fake_provider(prompt: str, image_bytes: bytes) -> bytes:
            if kind == "sleep":
                time.sleep(float(val))
                return PNG_1x1
            if kind == "hang":
                time.sleep(3600)
                return PNG_1x1
            raise RuntimeError("simulated provider failure")

        generation._call_provider = fake_provider
    else:
        generation.API_KEY = None

    import uvicorn  # noqa: E402
    from app.main import app  # noqa: E402

    print(json.dumps({"event": "backend_start", "tmp": str(tmp), "port": args.port, "ready": args.ready,
                      "provider": args.provider, "fallback_bytes": args.fallback_bytes}), flush=True)
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
