"""Deterministic upload fixture (seeded). python3 benchmarks/make_fixtures.py"""
from pathlib import Path
import numpy as np
from PIL import Image
out = Path(__file__).resolve().parent / "fixtures"; out.mkdir(exist_ok=True)
rng = np.random.default_rng(20261023)
h, w = 3024, 4032
y, x = np.mgrid[0:h, 0:w].astype(np.float32)
img = np.stack([128 + 100*np.sin(x/700), 128 + 100*np.cos(y/600), 128 + 80*np.sin((x+y)/1000)], -1) + rng.normal(0, 6, (h, w, 3))
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out / "upload-photo-4032x3024.jpg", quality=85)
print((out / "upload-photo-4032x3024.jpg").stat().st_size, "bytes")
