"""B2b: where the generate request's own CPU time goes, stage by stage.

In-process timing (no HTTP) of the functions POST /api/generate calls before
and after the model: validate_upload (magic bytes + Pillow decode/verify),
fingerprint (SHA-256 duplicate key), provider.build_request + json.dumps
(base64 encoding of the photo), and load_recipes (recipes.json read per request).

    apps/backend/.venv/bin/python benchmarks/bench_stages.py [--tag NAME]
    (MOSAIC_BENCH_SRC=<other apps/backend> to time another checkout)
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time

from harness import BACKEND_SRC, environment, jpeg, save

sys.path.insert(0, os.environ.get("MOSAIC_BENCH_SRC") or str(BACKEND_SRC))
from app import generation, provider, recipes  # noqa: E402
from app.limits import fingerprint  # noqa: E402


def timeit(fn, n):
    for _ in range(3):
        fn()
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    out.sort()
    return {"n": n, "median_ms": round(statistics.median(out), 3),
            "p95_ms": round(out[int(0.95 * (n - 1))], 3)}


def main():
    rows = []
    for label, (w, h) in {"0.3MP": (640, 480), "3MP": (2048, 1536), "12MP": (4032, 3024)}.items():
        photo = jpeg(w, h)
        n = 50 if label != "12MP" else 20
        stages = {
            "validate_upload": lambda photo=photo: generation.validate_upload(photo),
            "fingerprint_sha256": lambda photo=photo: fingerprint("seed-01", photo),
            "build_request_json": lambda photo=photo: json.dumps(
                provider.build_request("p" * 2000, photo, "jpg", "3:4")).encode(),
        }
        for stage, fn in stages.items():
            r = timeit(fn, n)
            r.update(photo=label, bytes=len(photo), stage=stage)
            rows.append(r)
            print(f"{label:6} {stage:20} median={r['median_ms']:8.3f}ms p95={r['p95_ms']:8.3f}ms")
    r = timeit(recipes.load_recipes, 500)
    r.update(photo=None, bytes=None, stage="load_recipes (per request)")
    rows.append(r)
    print(f"{'-':6} {'load_recipes':20} median={r['median_ms']:8.3f}ms p95={r['p95_ms']:8.3f}ms")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "stages"
    save(tag, {"benchmark": "B2b in-process stage timing", "environment": environment(),
                    "rows": rows})


if __name__ == "__main__":
    main()
