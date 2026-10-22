"""Alternatives for "is this upload a usable photo?" -- cost vs. what each catches.

Compares four ways to validate a JPEG upload before the paid model call:

  verify      Image.verify() -- what PR #2 ships. For JPEG it parses headers only.
  eoi         also require the JPEG end-of-image marker (FF D9) at the end.
  draft_load  Image.draft() to 1/8 scale, then load(): libjpeg walks the whole
              entropy-coded stream but skips most of the IDCT work.
  full_load   Image.load() at full resolution.

Corpus: one deterministic photo-like JPEG per size, plus damaged variants.

    apps/backend/.venv/bin/python benchmarks/compare_validation.py
"""

from __future__ import annotations

import io
import statistics
import time

from PIL import Image

from harness import environment, jpeg, save


def verify(data):
    with Image.open(io.BytesIO(data)) as img:
        img.verify()


def eoi(data):
    verify(data)
    if not data.rstrip(b"\x00").endswith(b"\xff\xd9"):
        raise ValueError("no end-of-image marker")


def draft_load(data):
    with Image.open(io.BytesIO(data)) as img:
        img.draft("RGB", (max(1, img.width // 8), max(1, img.height // 8)))
        img.load()


def full_load(data):
    with Image.open(io.BytesIO(data)) as img:
        img.load()


METHODS = {"verify": verify, "eoi": eoi, "draft_load": draft_load, "full_load": full_load}


def rejects(fn, data) -> bool:
    try:
        fn(data)
        return False
    except Exception:  # noqa: BLE001
        return True


def cost(fn, data, n):
    for _ in range(2):
        fn(data)
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn(data)
        out.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(out), 2)


def main():
    timing = []
    for label, (w, h) in {"0.3MP": (640, 480), "3MP": (2048, 1536), "12MP": (4032, 3024)}.items():
        photo = jpeg(w, h)
        for name, fn in METHODS.items():
            ms = cost(fn, photo, 30 if label == "12MP" else 60)
            timing.append({"photo": label, "bytes": len(photo), "method": name, "median_ms": ms})
            print(f"cost   {label:6} {name:11} {ms:8.2f} ms")

    base = jpeg(2048, 1536)
    corpus = {f"truncated to {int(f*100)}%": base[:int(len(base) * f)]
              for f in (0.99, 0.9, 0.5, 0.1, 0.01)}
    mid = bytearray(base)
    mid[len(mid) // 2: len(mid) // 2 + 20000] = b"\x00" * 20000
    corpus["20KB zeroed mid-file"] = bytes(mid)
    corpus["valid (control, must pass)"] = base
    corpus["valid + trailing bytes (must pass)"] = base + b"\x00trailer"
    detection = []
    for case, data in corpus.items():
        row = {"case": case, **{m: rejects(fn, data) for m, fn in METHODS.items()}}
        detection.append(row)
        print(f"reject {case:36} " + " ".join(f"{m}={row[m]!s:5}" for m in METHODS))
    save("validation_alternatives", {
        "benchmark": "Upload validation alternatives (in-process, Pillow)",
        "environment": environment(), "pillow": Image.__version__,
        "cost": timing, "detection": detection})


if __name__ == "__main__":
    main()
