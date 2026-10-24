"""Regression tests for defects found by benchmarks/ (see
docs/engineering-case-study/05-engineering-improvements.md).

1. A truncated JPEG passed validate_upload and reached the paid model.
2. The provider timeout bounded each socket read, not the whole call.
3. Identical requests that overlapped in time each paid for a generation.
4. Two processes writing the same LocalStore file collided on the tmp name.
"""

import base64
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image

from app import generation, limits, main, provider
from app import recipes as recipe_mod
from app.storage import LocalStore


def photo(fmt="JPEG", size=(640, 480)) -> bytes:
    img = Image.effect_noise(size, 60).convert("RGB")
    buf = BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


class TruncatedUploads(unittest.TestCase):
    def test_jpeg_cut_anywhere_is_invalid(self):
        data = photo()
        for frac in (0.99, 0.9, 0.5, 0.1):
            with self.subTest(frac=frac):
                self.assertEqual(generation.validate_upload(data[:int(len(data) * frac)]),
                                 "invalid_image")

    def test_webp_cut_short_is_invalid(self):
        data = photo("WEBP")
        self.assertEqual(generation.validate_upload(data[:len(data) // 2]), "invalid_image")

    def test_bytes_after_the_jpeg_end_marker_are_fine(self):
        # Phones append data after the image (e.g. motion photos); still valid.
        self.assertIsNone(generation.validate_upload(photo() + b"\x00trailer" * 100))

    def test_large_photo_still_passes(self):
        self.assertIsNone(generation.validate_upload(photo(size=(3000, 2000))))


class _Drip(BaseHTTPRequestHandler):
    """Answers at once, then sends the body one byte every 50 ms."""

    def log_message(self, *args):
        pass

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps({"output_image": {"data": base64.b64encode(b"x" * 64).decode()}})
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            for ch in body.encode():
                self.wfile.write(bytes([ch]))
                self.wfile.flush()
                time.sleep(0.05)
        except OSError:
            pass


class ProviderDeadline(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Drip)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        url = f"http://127.0.0.1:{self.server.server_address[1]}/v1beta/interactions"
        patcher = mock.patch.dict(os.environ, {"MOSAIC_PROVIDER_ENDPOINT": url,
                                               "MOSAIC_PROVIDER_TIMEOUT": "1"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_slow_drip_is_cut_off_at_the_deadline(self):
        # The full body would take ~6 s to arrive.
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            provider.generate("k", "p", photo(), "jpg", None)
        self.assertLess(time.monotonic() - started, 1.5)

    def test_timeout_maps_to_provider_timeout(self):
        with self.assertRaises(Exception) as caught:
            provider.generate("k", "p", photo(), "jpg", None)
        self.assertEqual(generation._reason_code(caught.exception), "provider_timeout")


class OverlappingDuplicates(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        data = recipe_mod.load_recipes()
        data[0]["tryReady"] = True
        recipes_file = tmp / "recipes.json"
        recipes_file.write_text(json.dumps(data), encoding="utf-8")
        self.calls = 0

        def slow_model(recipe, img):
            self.calls += 1
            time.sleep(0.5)
            return photo("PNG", (8, 8))

        env = {k: "" for k in ("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN",
                               "BLOB_STORE_ID", "VERCEL")}
        for p in (
            mock.patch.dict(os.environ, {**env, "MOSAIC_RATE_PER_MINUTE": "10",
                                         "MOSAIC_DAILY_PER_CLIENT": "10",
                                         "MOSAIC_DAILY_GLOBAL": "10",
                                         "MOSAIC_MAX_CONCURRENT": "2"}),
            mock.patch.object(recipe_mod, "RECIPES_FILE", recipes_file),
            mock.patch.multiple(generation, STORAGE=tmp, RESULTS_DIR=tmp / "results",
                                FALLBACK_DIR=tmp / "fallback", API_KEY="k",
                                _call_provider=slow_model),
        ):
            p.start()
            self.addCleanup(p.stop)
        main.limiter.reset()

    def post(self, img):
        with TestClient(main.app) as client:
            return client.post("/api/generate", data={"recipeId": "seed-01"},
                               files={"image": ("p.jpg", img, "image/jpeg")})

    def test_overlapping_identical_requests_pay_once(self):
        img = photo()
        with ThreadPoolExecutor(3) as pool:
            first = pool.submit(self.post, img)
            time.sleep(0.1)  # the second and third arrive while the first runs
            rest = [pool.submit(self.post, img) for _ in range(2)]
            responses = [first.result()] + [f.result() for f in rest]
        self.assertEqual([r.status_code for r in responses], [200, 200, 200])
        self.assertEqual(len({r.json()["resultId"] for r in responses}), 1)
        self.assertEqual(self.calls, 1)

    def test_different_photos_do_not_wait_for_each_other(self):
        with ThreadPoolExecutor(2) as pool:
            started = time.monotonic()
            a = pool.submit(self.post, photo(size=(64, 48)))
            b = pool.submit(self.post, photo(size=(48, 64)))
            self.assertNotEqual(a.result().json(), b.result().json())
        self.assertEqual(self.calls, 2)
        self.assertLess(time.monotonic() - started, 0.95)


class LeadUnit(unittest.TestCase):
    def test_waiter_cap(self):
        lim = limits.Limiter()
        self.assertEqual(lim.lead("k"), "lead")
        with mock.patch.object(limits.Limiter, "MAX_WAITERS", 0):
            self.assertEqual(lim.lead("k"), "bypass")
        lim.done("k")
        self.assertEqual(lim.lead("k"), "lead")

    def test_waiter_is_released_by_done(self):
        lim = limits.Limiter()
        lim.lead("k")
        threading.Timer(0.1, lim.done, ["k"]).start()
        started = time.monotonic()
        self.assertEqual(lim.lead("k"), "waited")
        self.assertLess(time.monotonic() - started, 1)


class ConcurrentLocalWrites(unittest.TestCase):
    def test_same_name_from_many_writers(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        store = LocalStore(root)
        errors = []

        def write(i):
            try:
                for _ in range(50):
                    store.put("usage.json", json.dumps({"n": i}).encode())
            except OSError as err:
                errors.append(err)

        with ThreadPoolExecutor(8) as pool:
            list(pool.map(write, range(8)))
        self.assertEqual(errors, [])
        self.assertIn("n", json.loads(store.get("usage.json")))
        self.assertEqual(list(root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
