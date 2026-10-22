"""Results store: local disk by default, Vercel Blob when a store is connected."""

import base64
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import generation, storage
from app import recipes as recipe_mod
from app.main import app

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def real_jpeg(size=(64, 48), color=(200, 120, 40)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


JPEG = real_jpeg()
NO_BLOB_ENV = {k: "" for k in ("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN",
                               "BLOB_STORE_ID", "VERCEL", "BLOB_ACCESS")}


class FakeBlobNotFound(Exception):
    pass


FakeBlobNotFound.__name__ = "BlobNotFoundError"


class FakeBlob:
    """Mimics vercel.blob.sync: put_blob / get_blob(...).body."""

    def __init__(self):
        self.items, self.calls = {}, []

    def put_blob(self, pathname, body, *, access, content_type=None,
                 add_random_suffix=False, allow_overwrite=False, **_):
        self.calls.append((pathname, access, content_type, add_random_suffix, allow_overwrite))
        self.items[pathname] = bytes(body)

    def get_blob(self, pathname, *, access):
        if pathname not in self.items:
            raise FakeBlobNotFound(pathname)
        return mock.Mock(body=self.items[pathname])


class Selection(unittest.TestCase):
    def test_local_by_default(self):
        with mock.patch.dict(os.environ, NO_BLOB_ENV):
            s = storage.results_store(Path("/x"))
        self.assertIsInstance(s, storage.LocalStore)
        self.assertEqual(s.root, Path("/x"))

    def test_vercel_without_blob_uses_tmp(self):
        with mock.patch.dict(os.environ, {**NO_BLOB_ENV, "VERCEL": "1"}):
            s = storage.results_store(Path("/x"))
        self.assertEqual(s.root, Path("/tmp/mosaic/results"))

    def test_blob_when_token_present(self):
        with mock.patch.dict(os.environ, {**NO_BLOB_ENV, "BLOB_READ_WRITE_TOKEN": "t"}):
            s = storage.results_store(Path("/x"))
        self.assertIsInstance(s, storage.BlobStore)
        self.assertEqual(s.access, "private")

    def test_blob_access_can_be_public(self):
        env = {**NO_BLOB_ENV, "BLOB_STORE_ID": "s", "BLOB_ACCESS": "public"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(storage.results_store(Path("/x")).access, "public")


class BlobStoreBehaviour(unittest.TestCase):
    def test_roundtrip_with_fixed_names(self):
        fake = FakeBlob()
        s = storage.BlobStore(fake)
        s.put("a" * 32 + ".png", PNG)
        self.assertEqual(s.get("a" * 32 + ".png"), PNG)
        pathname, access, ctype, suffix, overwrite = fake.calls[0]
        self.assertEqual(pathname, "results/" + "a" * 32 + ".png")
        self.assertEqual((access, ctype, suffix, overwrite), ("private", "image/png", False, True))

    def test_missing_blob_is_none(self):
        self.assertIsNone(storage.BlobStore(FakeBlob()).get("nope.json"))


class EndToEndThroughBlob(unittest.TestCase):
    """The whole result lifecycle with Blob as the store, over the HTTP API."""

    def setUp(self):
        self.fake = FakeBlob()
        self.recipes = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        data = recipe_mod.load_recipes()
        data[0]["tryReady"] = True
        import json
        json.dump(data, self.recipes)
        self.recipes.close()
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(os.unlink, self.recipes.name)
        for p in (
            mock.patch.object(recipe_mod, "RECIPES_FILE", Path(self.recipes.name)),
            mock.patch.multiple(generation, RESULTS_DIR=tmp / "results",
                                FALLBACK_DIR=tmp / "fallback", API_KEY="k",
                                _call_provider=mock.Mock(return_value=PNG)),
            mock.patch.object(storage, "results_store",
                              lambda _root, **_kw: storage.BlobStore(self.fake)),
            mock.patch.object(generation, "results_store",
                              lambda _root, **_kw: storage.BlobStore(self.fake)),
        ):
            p.start()
            self.addCleanup(p.stop)
        from app import main
        main.limiter.reset()
        self.client = TestClient(app)

    def test_generate_fetch_and_serve_image(self):
        r = self.client.post("/api/generate", data={"recipeId": "seed-01"},
                             files={"image": ("p.jpg", JPEG, "image/jpeg")})
        self.assertEqual(r.status_code, 200, r.text)
        rid = r.json()["resultId"]
        result = self.client.get(f"/api/results/{rid}").json()
        self.assertEqual(result["mode"], "live")
        self.assertEqual(result["imageUrl"], f"/static/results/{rid}.png")
        img = self.client.get(result["imageUrl"])
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img.headers["content-type"], "image/png")
        self.assertEqual(img.content, PNG)
        self.assertIn(f"results/{rid}.json", self.fake.items)
        self.assertIn(f"results/{rid}.png", self.fake.items)

    def test_image_route_rejects_non_result_names(self):
        for bad in ("../../app/main.py", "x.png", "a" * 32 + ".json", "a" * 32 + ".gif"):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.get(f"/static/results/{bad}").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
