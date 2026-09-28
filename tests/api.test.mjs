import { test, mock } from "node:test";
import assert from "node:assert/strict";
import {
  createMosaicClient,
  MosaicApiError,
  isGenerationResult,
  messageFor,
} from "../packages/api/src/client.ts";
import { MAX_IMAGE_BYTES, validateImage } from "../packages/core/src/index.ts";
const resultId = "a".repeat(32);
const recipe = {
  id: "seed-01",
  title: "Recipe",
  summary: "Summary",
  sourcePostUrl: "https://example.com/post",
  creatorName: null,
  creatorInstagramUrl: null,
  previewImageUrl: null,
  inputNote: "One photo",
  tryReady: false,
};
const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
test("public list uses the real API envelope and retains unverified fields", async () => {
  const api = createMosaicClient({
    fetch: async (url) => {
      assert.equal(url, "/api/recipes");
      return json({ recipes: [recipe] });
    },
  });
  assert.deepEqual(await api.listRecipes(), [recipe]);
});
test("multipart sends only recipeId + image, with browser-generated content type and a 75-second timeout", async () => {
  const durations = [];
  const timer = mock.method(AbortSignal, "timeout", (duration) => {
    durations.push(duration);
    return new AbortController().signal;
  });
  try {
    const file = new File(["image"], "photo.png", { type: "image/png" });
    const api = createMosaicClient({
      fetch: async (url, init) => {
        assert.equal(url, "/api/generate");
        assert.equal(init.method, "POST");
        assert.equal(init.headers, undefined);
        assert.deepEqual([...init.body.keys()], ["recipeId", "image"]);
        assert.equal(init.body.get("recipeId"), "seed-01");
        assert.equal(init.body.get("image").name, file.name);
        assert.ok(init.signal instanceof AbortSignal);
        return json({ resultId });
      },
    });
    assert.equal(await api.generate("seed-01", file), resultId);
    assert.deepEqual(durations, [75_000]);
  } finally {
    timer.mock.restore();
  }
});
test("all documented error codes are preserved and mapped", async () => {
  for (const [code, status] of [
    ["missing_recipe_id", 400],
    ["missing_image", 400],
    ["unsupported_type", 400],
    ["too_large", 400],
    ["recipe_not_ready", 403],
    ["unknown_recipe", 404],
    ["unknown_result", 404],
  ]) {
    const api = createMosaicClient({
      fetch: async () => json({ error: code }, status),
    });
    await assert.rejects(
      api.getRecipe("seed-01"),
      (e) =>
        e instanceof MosaicApiError &&
        e.code === code &&
        e.status === status &&
        typeof messageFor(e) === "string",
    );
  }
});
test("network failure and proxy 500 with failed health become backend_unavailable", async () => {
  for (const response of [
    () => {
      throw new TypeError("offline");
    },
    () => new Response("Bad Gateway", { status: 502 }),
  ]) {
    const api = createMosaicClient({
      fetch: async (url) =>
        url === "/api/health" ? json({ ok: false }, 503) : response(),
    });
    await assert.rejects(api.listRecipes(), { code: "backend_unavailable" });
  }
});
test("network failure while health succeeds is a request failure", async () => {
  const api = createMosaicClient({
    fetch: async (url) => {
      if (url === "/api/health") return json({ ok: true });
      throw new TypeError("offline");
    },
  });
  await assert.rejects(api.listRecipes(), { code: "request_failed" });
});
test("timeouts check health and never retry generation", async () => {
  for (const alive of [true, false]) {
    const calls = [];
    const api = createMosaicClient({
      fetch: async (url) => {
        calls.push(url);
        if (url === "/api/health") return json({ ok: alive });
        throw new DOMException("deadline", "TimeoutError");
      },
    });
    await assert.rejects(
      api.generate(
        "seed-01",
        new File(["image"], "photo.png", { type: "image/png" }),
      ),
      { code: alive ? "request_timeout" : "backend_unavailable" },
    );
    assert.deepEqual(calls, ["/api/generate", "/api/health"]);
  }
});
test("malformed JSON/envelopes and invalid IDs are rejected", async () => {
  const api = createMosaicClient({
    fetch: async () => json({ recipes: [{ ...recipe, tryReady: "false" }] }),
  });
  await assert.rejects(api.listRecipes(), { code: "invalid_response" });
  let calls = 0;
  const invalid = createMosaicClient({
    fetch: async () => {
      calls++;
      return json({});
    },
  });
  await assert.rejects(invalid.getResult("../private"), {
    code: "unknown_result",
  });
  assert.equal(calls, 0);
});
test("live/cached/mock preserve sourceNote exactly, with truthful image availability", async () => {
  for (const mode of ["live", "cached", "mock"]) {
    const result = {
      resultId,
      recipeId: "seed-01",
      mode,
      sourceNote: "原樣：不可改寫\n第二行",
      imageUrl: mode === "mock" ? null : "/static/results/test.png",
      fallbackReason: mode === "live" ? null : "provider failed",
      recipeTitle: "Recipe",
      creatorName: null,
      sourcePostUrl: "https://example.com/post",
      creatorInstagramUrl: null,
      createdAt: "2026-09-28T00:00:00Z",
    };
    assert.ok(isGenerationResult(result));
    const api = createMosaicClient({ fetch: async () => json(result) });
    assert.deepEqual(await api.getResult(resultId), result);
    assert.equal(
      isGenerationResult({ ...result, mode: "mock", imageUrl: "/fake.png" }),
      false,
    );
  }
});
test("upload accepts <=8 MiB JPEG/PNG/WebP, rejects larger/empty/wrong formats", () => {
  for (const type of ["image/jpeg", "image/png", "image/webp"])
    assert.equal(validateImage({ size: MAX_IMAGE_BYTES, type }), null);
  assert.equal(
    validateImage({ size: MAX_IMAGE_BYTES + 1, type: "image/png" }),
    "too_large",
  );
  assert.equal(
    validateImage({ size: 1, type: "image/gif" }),
    "unsupported_type",
  );
  assert.equal(validateImage(null), "missing_image");
  assert.equal(validateImage({ size: 0, type: "image/png" }), "missing_image");
});
