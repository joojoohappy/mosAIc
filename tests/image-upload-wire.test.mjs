// Every test in api.test.mjs mocks fetch -- it proves the client BUILDS a
// correct request, never that a correct request actually survives real HTTP
// and lands intact at FastAPI's Form()/UploadFile parsing. That's the gap
// this file closes: the real @mosaic/api client, real undici fetch, real
// multipart wire encoding, against a real backend process.
//
// The backend runs from an isolated temp copy of app/ + data/, never the
// repo's own apps/backend/, so this can't collide with a human's dev.sh (this
// session hit exactly that class of bug three times tonight) and never
// mutates the real data/recipes.json even though it flips tryReady to
// exercise the accept path.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { cp, mkdtemp, rm, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:net";
import { createMosaicClient, MosaicApiError } from "../packages/api/src/client.ts";

const REPO_ROOT = new URL("..", import.meta.url).pathname;
const VENV_PYTHON = join(REPO_ROOT, "apps/backend/.venv/bin/python");

// The exact 1x1 PNG apps/backend/tests/test_generation.py uses -- same fixture,
// one definition, so "is this bytes-identical" is never a question when a
// failure shows up on either side of the wire.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function freePort() {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

let proc, tmp, baseUrl, api, readyRecipeId, notReadyRecipeId;

before(async () => {
  const venvOk = await readFile(VENV_PYTHON).then(
    () => true,
    () => false,
  );
  if (!venvOk) {
    throw new Error(
      "apps/backend/.venv missing -- run: python3 -m venv apps/backend/.venv " +
        "&& apps/backend/.venv/bin/pip install -r apps/backend/requirements.txt",
    );
  }

  tmp = await mkdtemp(join(tmpdir(), "mosaic-wire-"));
  await cp(join(REPO_ROOT, "apps/backend/app"), join(tmp, "app"), { recursive: true });
  await cp(join(REPO_ROOT, "apps/backend/data"), join(tmp, "data"), { recursive: true });

  // Flip exactly one recipe's tryReady in the COPY only. The shipped file (all
  // three false, per SEED-RECIPES.md -- nobody has verified a basis to run
  // them yet) is never touched.
  const recipesPath = join(tmp, "data/recipes.json");
  const recipes = JSON.parse(await readFile(recipesPath, "utf8"));
  recipes[0].tryReady = true;
  readyRecipeId = recipes[0].id;
  notReadyRecipeId = recipes[1].id;
  await writeFile(recipesPath, JSON.stringify(recipes));

  const port = await freePort();
  baseUrl = `http://127.0.0.1:${port}`;
  proc = spawn(
    VENV_PYTHON,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)],
    { cwd: tmp, stdio: "ignore" },
  );

  const deadline = Date.now() + 15_000;
  for (;;) {
    if (await fetch(baseUrl + "/api/health").then((r) => r.ok, () => false)) break;
    if (Date.now() > deadline) throw new Error("backend did not come up in time");
    if (proc.exitCode !== null) throw new Error("backend exited during startup");
    await new Promise((r) => setTimeout(r, 100));
  }

  api = createMosaicClient({ baseUrl });
});

after(async () => {
  proc?.kill();
  if (tmp) await rm(tmp, { recursive: true, force: true });
});

test("a real image, sent through the real client over real HTTP, produces a correct, self-consistent result", async () => {
  const file = new File([PNG], "photo.png", { type: "image/png" });
  const resultId = await api.generate(readyRecipeId, file);
  assert.match(resultId, /^[0-9a-f]{32}$/);

  const result = await api.getResult(resultId);
  assert.equal(result.recipeId, readyRecipeId);
  // No provider is configured in this environment, so the honest outcome is
  // mock -- this pins that the backend didn't silently fabricate a "live" or
  // "cached" claim just because a well-formed image arrived.
  assert.equal(result.mode, "mock");
  assert.equal(result.imageUrl, null);
  assert.ok(result.sourceNote.length > 0);
  assert.equal(result.fallbackReason, "no_api_key");

  // Refetch by ID: the wire-level ID handed back to the frontend must be the
  // same one that reads the same result back (this is what the Result page
  // actually does after a refresh).
  assert.deepEqual(await api.getResult(resultId), result);
});

test("corrupt image bytes are rejected by the real backend's magic-byte check, not silently accepted", async () => {
  const file = new File([Buffer.from("not a real image")], "photo.png", {
    type: "image/png",
  });
  await assert.rejects(api.generate(readyRecipeId, file), {
    code: "unsupported_type",
  });
});

test("an 8MB+1 image is rejected for size before the backend touches its content", async () => {
  const oversized = Buffer.concat([PNG, Buffer.alloc(8 * 1024 * 1024)]);
  const file = new File([oversized], "photo.png", { type: "image/png" });
  await assert.rejects(api.generate(readyRecipeId, file), { code: "too_large" });
});

test("a recipe nobody has verified (tryReady=false, the real shipped default) refuses generation over the real wire", async () => {
  const file = new File([PNG], "photo.png", { type: "image/png" });
  await assert.rejects(api.generate(notReadyRecipeId, file), (e) => {
    assert.ok(e instanceof MosaicApiError);
    assert.equal(e.code, "recipe_not_ready");
    assert.equal(e.status, 403);
    return true;
  });
});

test("an unknown recipe id is rejected before the upload is processed", async () => {
  const file = new File([PNG], "photo.png", { type: "image/png" });
  await assert.rejects(api.generate("seed-does-not-exist", file), {
    code: "unknown_recipe",
  });
});
