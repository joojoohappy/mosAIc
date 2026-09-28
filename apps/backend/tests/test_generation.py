"""Unit tests for the generation pipeline.

    cd backend && python -m unittest

stdlib unittest on purpose: pytest would be nicer to read and is one more thing to
install on a laptop at 9am on Build Day.

Every test isolates the filesystem into a tmpdir, so running these never touches
storage/ and can never leave a fabricated provenance sidecar behind.
"""

import base64
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import generation as generate
from app import recipes as recipe_mod

# A real 1x1 PNG: these bytes are written to disk and served, so use a valid file.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 32


class Base(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.fallback, self.results = tmp / "fallback", tmp / "results"
        self.fallback.mkdir()
        self.results.mkdir()
        patcher = mock.patch.multiple(
            generate, STORAGE=tmp, FALLBACK_DIR=self.fallback,
            RESULTS_DIR=self.results, API_KEY=None,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, tmp, True)
        self.recipe = recipe_mod.get_recipe("seed-01")

    def add_fallback(self, rid="seed-01", img=PNG, **override):
        meta = {
            "image": f"{rid}.png", "provider": "acme", "model": "m-1",
            "generatedAt": "2026-09-19T20:11:00Z", "inputPhoto": "dog.jpg",
            "durationSec": 20.0,
        }
        meta.update(override)
        if img is not None:
            (self.fallback / f"{rid}.png").write_bytes(img)
        (self.fallback / f"{rid}.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta


class ImageSniffing(Base):
    """Content-Type is client-supplied. Only the bytes decide."""

    def test_recognises_real_formats(self):
        self.assertEqual(generate._is_image(JPEG), "jpg")
        self.assertEqual(generate._is_image(PNG), "png")
        self.assertEqual(generate._is_image(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "webp")

    def test_rejects_non_images(self):
        for junk in (b"", b"<html>nope</html>", b"{\"error\":\"refused\"}",
                     b"RIFF\x00\x00\x00\x00NOPEVP8 ", b"\xff\xd8"):
            self.assertIsNone(generate._is_image(junk), junk[:12])


class RecipeLookup(Base):
    def test_three_seeds_with_prompts(self):
        ids = [r["id"] for r in recipe_mod.load_recipes()]
        self.assertEqual(ids, ["seed-01", "seed-02", "seed-03"])
        for r in recipe_mod.load_recipes():
            self.assertTrue(r["prompt"].strip(), f"{r['id']} has no prompt")
            self.assertTrue(r["sourcePostUrl"].startswith("https://"))

    def test_unknown_recipe_returns_none(self):
        self.assertIsNone(recipe_mod.get_recipe("seed-99"))
        self.assertIsNone(recipe_mod.get_recipe(""))

    def test_creator_fields_are_still_unverified(self):
        # Guards the honesty rule: nobody has checked the Threads posts yet, so no
        # name or IG may appear in the data. Flip this test when they are verified.
        for r in recipe_mod.load_recipes():
            self.assertIsNone(r["creatorName"], f"{r['id']} has an unverified name")
            self.assertIsNone(r["creatorInstagramUrl"], f"{r['id']} has an unverified IG")


class PublicProjection(Base):
    """The structural guarantee that prompt text cannot reach a client."""

    def test_prompt_is_never_in_the_projection(self):
        for r in recipe_mod.load_recipes():
            with self.subTest(recipe=r["id"]):
                self.assertNotIn("prompt", recipe_mod.public_recipe(r))

    def test_projection_is_an_allowlist_not_a_denylist(self):
        # A private field added to recipes.json later must stay private by default.
        leaked = recipe_mod.public_recipe({**self.recipe, "internalNote": "secret"})
        self.assertNotIn("internalNote", leaked)

    def test_projection_shape_is_stable_even_when_a_field_is_absent(self):
        # The frontend codes against a fixed shape; a thin record still yields
        # every key, with null for what is missing.
        thin = recipe_mod.public_recipe({"id": "seed-01"})
        self.assertEqual(set(thin), set(recipe_mod.PUBLIC_FIELDS))
        self.assertIsNone(thin["tryReady"])

    def test_projection_carries_what_the_gallery_needs(self):
        p = recipe_mod.public_recipe(self.recipe)
        for field in ("id", "title", "summary", "sourcePostUrl", "tryReady"):
            self.assertIn(field, p)


class TryReadiness(Base):
    def test_every_seed_is_still_unverified(self):
        # Nobody has established a basis for running these prompts yet, so the
        # honest default is false. When you flip one, flip it here too -- and be
        # ready to say what the evidence was.
        for r in recipe_mod.load_recipes():
            self.assertFalse(r["tryReady"], f"{r['id']} claims tryReady without evidence")

    def test_preview_images_are_still_absent(self):
        for r in recipe_mod.load_recipes():
            self.assertIsNone(r["previewImageUrl"], f"{r['id']} has an uncleared preview")


class SidecarValidation(Base):
    """A sidecar is a claim about provenance. Only a complete, backed one counts."""

    def test_valid_sidecar_accepted(self):
        self.add_fallback()
        self.assertIsNotNone(generate._read_sidecar("seed-01"))

    def test_absent_is_none(self):
        self.assertIsNone(generate._read_sidecar("seed-01"))

    def test_missing_field_degrades(self):
        for field in ("provider", "model", "generatedAt", "inputPhoto", "image"):
            with self.subTest(field=field):
                self.add_fallback(**{field: None})
                self.assertIsNone(generate._read_sidecar("seed-01"))

    def test_corrupt_json_degrades(self):
        self.add_fallback()
        (self.fallback / "seed-01.json").write_text("{ not json", encoding="utf-8")
        self.assertIsNone(generate._read_sidecar("seed-01"))

    def test_sidecar_without_its_image_degrades(self):
        self.add_fallback(img=None)
        self.assertIsNone(generate._read_sidecar("seed-01"))

    def test_fallback_that_is_not_an_image_degrades(self):
        # A truncated or half-written fallback would otherwise be served as
        # "cached" with a note claiming a real generation produced it.
        self.add_fallback(img=b"<html>provider error page</html>")
        self.assertIsNone(generate._read_sidecar("seed-01"))

    def test_truncated_png_degrades(self):
        self.add_fallback(img=PNG[:4])
        self.assertIsNone(generate._read_sidecar("seed-01"))

    def test_empty_fallback_file_degrades(self):
        self.add_fallback(img=b"")
        self.assertIsNone(generate._read_sidecar("seed-01"))

    def test_corrupt_fallback_falls_through_to_mock_not_cached(self):
        self.add_fallback(img=b"not an image")
        r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(r["mode"], "mock")
        self.assertIsNone(r["imageUrl"])

    def test_image_path_cannot_escape_fallback_dir(self):
        self.add_fallback(image="../../../etc/passwd")
        self.assertIsNone(generate._read_sidecar("seed-01"))


class Modes(Base):
    def test_no_key_no_fallback_is_mock(self):
        r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(r["mode"], "mock")
        self.assertIsNone(r["imageUrl"])
        self.assertEqual(r["fallbackReason"], "no_api_key")

    def test_no_key_with_fallback_is_cached(self):
        meta = self.add_fallback()
        r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(r["mode"], "cached")
        self.assertTrue(r["imageUrl"].startswith("/static/results/"))
        for claim in (meta["provider"], meta["model"], meta["inputPhoto"], meta["generatedAt"]):
            self.assertIn(claim, r["sourceNote"], "provenance must be quoted, not summarised")

    def test_working_provider_is_live(self):
        with mock.patch.multiple(generate, API_KEY="k",
                                 _call_provider=mock.Mock(return_value=PNG)):
            r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(r["mode"], "live")
        self.assertIsNone(r["fallbackReason"])
        self.assertIn("即時生成", r["sourceNote"])

    def test_provider_error_falls_back_and_records_why(self):
        self.add_fallback()
        boom = mock.Mock(side_effect=TimeoutError("deadline exceeded"))
        with mock.patch.multiple(generate, API_KEY="k", _call_provider=boom):
            r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(r["mode"], "cached")
        self.assertIn("TimeoutError", r["fallbackReason"])

    def test_provider_returning_text_is_not_live(self):
        # A 200 carrying a refusal message is a failure, not an image.
        self.add_fallback()
        with mock.patch.multiple(generate, API_KEY="k",
                                 _call_provider=mock.Mock(return_value=b'{"refused":1}')):
            r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(r["mode"], "cached")
        self.assertIn("not an image", r["fallbackReason"])

    def test_provider_is_given_the_stored_prompt_not_the_caller_input(self):
        spy = mock.Mock(return_value=PNG)
        with mock.patch.multiple(generate, API_KEY="k", _call_provider=spy):
            generate.run_generation(self.recipe, JPEG)
        spy.assert_called_once_with(self.recipe["prompt"], JPEG)


class Disclosure(Base):
    """The invariants that stop the UI from lying."""

    def test_fallback_never_claims_the_users_photo(self):
        # Substring-matching "你這次上傳" is useless here: the honest sentence contains
        # it inside a negation. Assert the negation is present and the live-only
        # phrase is absent.
        self.add_fallback()
        note = generate.run_generation(self.recipe, JPEG)["sourceNote"]
        self.assertIn("不是由你這次上傳的照片", note)
        self.assertNotIn("即時生成", note)

    def test_image_url_is_null_exactly_when_mock(self):
        self.assertIsNone(generate.run_generation(self.recipe, JPEG)["imageUrl"])
        self.add_fallback()
        self.assertIsNotNone(generate.run_generation(self.recipe, JPEG)["imageUrl"])

    def test_non_live_results_always_say_why(self):
        self.add_fallback()
        self.assertTrue(generate.run_generation(self.recipe, JPEG)["fallbackReason"])

    def test_attribution_survives_to_the_result(self):
        r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(r["recipeId"], self.recipe["id"])
        self.assertEqual(r["sourcePostUrl"], self.recipe["sourcePostUrl"])
        self.assertEqual(r["recipeTitle"], self.recipe["title"])


class ResultStore(Base):
    def test_roundtrip(self):
        r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual(generate.load_result(r["resultId"]), r)

    def test_rejects_ids_that_are_not_32_hex(self):
        for bad in ("../../etc/passwd", "nope", "", "A" * 32, "a" * 31, "a" * 33):
            with self.subTest(bad=bad):
                self.assertIsNone(generate.load_result(bad))

    def test_unknown_id_is_none_not_an_error(self):
        self.assertIsNone(generate.load_result("0" * 32))

    def test_no_temp_file_left_behind(self):
        generate.run_generation(self.recipe, JPEG)
        self.assertEqual(list(self.results.glob("*.tmp")), [])

    def test_only_write_result_touches_disk(self):
        # A provider that dies mid-call must leave nothing behind: every write happens
        # once, after the mode is decided.
        boom = mock.Mock(side_effect=RuntimeError("died"))
        with mock.patch.multiple(generate, API_KEY="k", _call_provider=boom):
            r = generate.run_generation(self.recipe, JPEG)
        self.assertEqual([p.name for p in self.results.iterdir()], [f"{r['resultId']}.json"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
