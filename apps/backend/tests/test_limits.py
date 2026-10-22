"""Upload validation, rate limits, daily budget, duplicate protection, body cap."""

import json
import os
import shutil
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image

from app import generation, limits, main
from app import recipes as recipe_mod


def photo(fmt="JPEG", size=(64, 48), color=(10, 120, 200)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


class UploadValidation(unittest.TestCase):
    def test_real_photos_pass(self):
        for fmt in ("JPEG", "PNG", "WEBP"):
            with self.subTest(fmt=fmt):
                self.assertIsNone(generation.validate_upload(photo(fmt)))

    def test_renamed_text_is_unsupported(self):
        self.assertEqual(generation.validate_upload(b"hello"), "unsupported_type")

    def test_heic_is_unsupported(self):
        heic = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64
        self.assertEqual(generation.validate_upload(heic), "unsupported_type")

    def test_truncated_photo_is_invalid(self):
        self.assertEqual(generation.validate_upload(photo()[:40]), "invalid_image")

    def test_decompression_bomb_is_invalid(self):
        with mock.patch.object(generation, "MAX_PIXELS", 100):
            self.assertEqual(generation.validate_upload(photo(size=(20, 20))), "invalid_image")


class LimiterUnit(unittest.TestCase):
    def setUp(self):
        self.l = limits.Limiter()

    def test_per_minute_then_daily(self):
        env = {"MOSAIC_RATE_PER_MINUTE": "2", "MOSAIC_DAILY_PER_CLIENT": "3"}
        with mock.patch.dict(os.environ, env):
            self.assertIsNone(self.l.admit("a"))
            self.assertIsNone(self.l.admit("a"))
            self.assertEqual(self.l.admit("a"), "rate_limited")
            self.assertIsNone(self.l.admit("b"), "visitors are counted separately")
            self.l._minute["a"].clear()  # a minute passes
            self.assertIsNone(self.l.admit("a"))
            self.l._minute["a"].clear()
            self.assertEqual(self.l.admit("a"), "daily_limit_reached")

    def test_concurrency_gate(self):
        with mock.patch.dict(os.environ, {"MOSAIC_MAX_CONCURRENT": "1"}):
            self.assertTrue(self.l.acquire())
            self.assertFalse(self.l.acquire())
            self.l.release()
            self.assertTrue(self.l.acquire())

    def test_bad_env_values_fall_back_to_defaults(self):
        with mock.patch.dict(os.environ, {"MOSAIC_DAILY_GLOBAL": "lots"}):
            self.assertEqual(limits.settings()["daily_global"], 50)

    def test_client_id_prefers_first_forwarded_hop(self):
        forwarded = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
        self.assertEqual(limits.client_id(forwarded, "9.9.9.9"), "1.2.3.4")
        self.assertEqual(limits.client_id({}, "9.9.9.9"), "9.9.9.9")


class ApiLimits(unittest.TestCase):
    """Through the real HTTP app with a stubbed model."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        data = recipe_mod.load_recipes()
        data[0]["tryReady"] = True
        recipes_file = tmp / "recipes.json"
        recipes_file.write_text(json.dumps(data), encoding="utf-8")
        self.provider = mock.Mock(side_effect=lambda recipe, img: photo("PNG"))
        env = {k: "" for k in ("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN",
                               "BLOB_STORE_ID", "VERCEL")}
        for p in (
            mock.patch.dict(os.environ, {**env, "MOSAIC_RATE_PER_MINUTE": "3",
                                         "MOSAIC_DAILY_PER_CLIENT": "10",
                                         "MOSAIC_DAILY_GLOBAL": "2",
                                         "MOSAIC_MAX_CONCURRENT": "2"}),
            mock.patch.object(recipe_mod, "RECIPES_FILE", recipes_file),
            mock.patch.multiple(generation, STORAGE=tmp, RESULTS_DIR=tmp / "results",
                                FALLBACK_DIR=tmp / "fallback", API_KEY="k",
                                _call_provider=self.provider),
        ):
            p.start()
            self.addCleanup(p.stop)
        main.limiter.reset()
        self.client = TestClient(main.app)

    def post(self, img=None, recipe="seed-01"):
        return self.client.post("/api/generate", data={"recipeId": recipe},
                                files={"image": ("p.jpg", img or photo(), "image/jpeg")})

    def test_same_photo_twice_is_one_paid_call(self):
        a, b = self.post(), self.post()
        self.assertEqual(a.status_code, 200)
        self.assertEqual(a.json(), b.json())
        self.assertEqual(self.provider.call_count, 1)

    def test_rate_limit_returns_429(self):
        codes = [self.post(photo(color=(60 * i, 0, 0))).status_code for i in range(4)]
        # 2 paid calls fit today's budget, the 3rd hits it, the 4th the minute limit.
        self.assertEqual(codes, [200, 200, 503, 429])
        self.assertEqual(self.post(photo(color=(9, 9, 9))).json(), {"error": "rate_limited"})

    def test_global_budget_stops_paid_calls(self):
        self.post(photo(color=(50, 50, 50)))
        self.post(photo(color=(150, 150, 150)))
        r = self.post(photo(color=(250, 250, 250)))
        self.assertEqual((r.status_code, r.json()), (503, {"error": "daily_budget_reached"}))
        self.assertEqual(self.provider.call_count, 2)
        usage = generation.budget.usage()
        self.assertEqual((usage["attempts"], usage["live"]), (2, 2))

    def test_invalid_image_never_reaches_the_model(self):
        r = self.post(photo()[:50])
        self.assertEqual((r.status_code, r.json()), (400, {"error": "invalid_image"}))
        self.provider.assert_not_called()

    def test_oversized_upload_is_413(self):
        big = photo() + b"\0" * (generation.MAX_BYTES + 1)
        r = self.post(big)
        self.assertEqual((r.status_code, r.json()), (413, {"error": "too_large"}))

    def test_body_cap_rejects_before_parsing(self):
        r = self.client.post("/api/generate", content=b"x" * (main.MAX_REQUEST_BYTES + 10),
                             headers={"content-type": "application/octet-stream"})
        self.assertEqual((r.status_code, r.json()), (413, {"error": "too_large"}))

    def test_provider_failure_detail_stays_in_the_log(self):
        self.provider.side_effect = RuntimeError("secret upstream detail")
        rid = self.post().json()["resultId"]
        result = self.client.get(f"/api/results/{rid}").json()
        self.assertEqual(result["fallbackReason"], "provider_error")
        self.assertNotIn("secret", json.dumps(result))

    def test_fallback_sidecars_are_not_served(self):
        self.assertEqual(self.client.get("/static/fallback/seed-01.json").status_code, 404)
        self.assertEqual(self.client.get("/static/results/" + "a" * 32 + ".json").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
