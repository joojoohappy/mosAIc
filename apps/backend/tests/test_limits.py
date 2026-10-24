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

    def test_client_id_ignores_forwarded_for(self):
        spoofed = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
        with mock.patch.dict(os.environ, {"VERCEL": "", "MOSAIC_PROXY_SECRET": "",
                                          "MOSAIC_TRUST_X_REAL_IP": ""}):
            self.assertEqual(limits.client_id(spoofed, "9.9.9.9"), "peer:9.9.9.9")
            # x-real-ip is only trusted where the platform sets it.
            self.assertEqual(limits.client_id({"x-real-ip": "5.5.5.5"}, "9.9.9.9"),
                             "peer:9.9.9.9")
        with mock.patch.dict(os.environ, {"VERCEL": "1", "MOSAIC_PROXY_SECRET": ""}):
            self.assertEqual(limits.client_id({"x-real-ip": "5.5.5.5", **spoofed}, "9"),
                             "ip:5.5.5.5")

    def test_client_ip_from_website_needs_the_secret(self):
        sent = {"x-mosaic-client-ip": "7.7.7.7", "x-mosaic-proxy-secret": "s3cret"}
        forged = {**sent, "x-mosaic-proxy-secret": "guess"}
        with mock.patch.dict(os.environ, {"VERCEL": "", "MOSAIC_PROXY_SECRET": "s3cret",
                                          "MOSAIC_TRUST_X_REAL_IP": ""}):
            self.assertEqual(limits.client_id(sent, "9.9.9.9"), "ip:7.7.7.7")
            self.assertEqual(limits.client_id(forged, "9.9.9.9"), "peer:9.9.9.9")
        with mock.patch.dict(os.environ, {"VERCEL": "", "MOSAIC_PROXY_SECRET": ""}):
            # No secret configured: the header is ignored entirely.
            self.assertEqual(limits.client_id(sent, "9.9.9.9"), "peer:9.9.9.9")


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

    def test_spoofed_forwarded_for_does_not_reset_the_limit(self):
        codes = []
        for i in range(4):
            r = self.client.post(
                "/api/generate", data={"recipeId": "seed-01"},
                files={"image": ("p.jpg", photo(color=(0, 60 * i, 0)), "image/jpeg")},
                headers={"x-forwarded-for": f"203.0.113.{i}",
                         "x-mosaic-client-ip": f"198.51.100.{i}"})
            codes.append(r.status_code)
        # Same visitor every time despite four different made-up addresses.
        self.assertEqual(codes[-1], 429)

    def test_vercel_without_blob_never_pays(self):
        with mock.patch.dict(os.environ, {"VERCEL": "1"}):
            self.assertFalse(self.client.get("/api/health").json()["liveGeneration"])
            rid = self.post().json()["resultId"]
            result = self.client.get(f"/api/results/{rid}").json()
        self.assertEqual(result["fallbackReason"], "no_shared_storage")
        self.provider.assert_not_called()

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

    def test_body_cap_rejects_chunked_upload_with_the_contract_error(self):
        # No Content-Length: the cap is hit while streaming. The client maps the
        # error CODE to its message, so FastAPI's generic 400 "error parsing the
        # body" is not good enough; it must be the documented 413 too_large.
        def chunks():
            for _ in range((main.MAX_REQUEST_BYTES // 65536) + 4):
                yield b"x" * 65536

        r = self.client.post("/api/generate", content=chunks(),
                             headers={"content-type": "multipart/form-data; boundary=b"})
        self.assertEqual((r.status_code, r.json()), (413, {"error": "too_large"}))
        self.provider.assert_not_called()

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
