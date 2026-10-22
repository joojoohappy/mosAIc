// Full user journey in a real browser: Next.js (dev) + FastAPI + a fake image
// model, all on free local ports. The real Gemini API is replaced by a tiny
// HTTP server that speaks the same response shape, so the provider code path
// (request building, HTTP, response parsing) runs for real.
//
//   pnpm test:e2e
//
// Needs apps/backend/.venv (see README) and a Chromium for Playwright:
//   pnpm exec playwright-core install chromium
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer as createHttpServer } from "node:http";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { crc32 } from "node:zlib";
import { join } from "node:path";
import { chromium } from "playwright-core";

const ROOT = new URL("../..", import.meta.url).pathname;
const PYTHON = join(ROOT, "apps/backend/.venv/bin/python");
// 2x2 red PNG returned by the fake model.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AARAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg==",
  "base64",
);
const children = [];
let fakeMode = "ok";
let tmp,
  fake,
  web,
  browser,
  modelCalls = [];

const freePort = () =>
  new Promise((resolve, reject) => {
    const srv = createServer();
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });

async function waitFor(url, ms, proc) {
  const deadline = Date.now() + ms;
  for (;;) {
    if (
      await fetch(url).then(
        (r) => r.ok,
        () => false,
      )
    )
      return;
    if (proc && proc.exitCode !== null)
      throw new Error(`${url}: process exited`);
    if (Date.now() > deadline) throw new Error(`${url} did not come up`);
    await new Promise((r) => setTimeout(r, 250));
  }
}

before(async () => {
  // Fake image model.
  fake = createHttpServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      modelCalls.push({
        key: req.headers["x-goog-api-key"],
        body: JSON.parse(body),
      });
      const reply = () => {
        res.setHeader("Content-Type", "application/json");
        res.end(
          JSON.stringify({ output_image: { data: PNG.toString("base64") } }),
        );
      };
      // fakeMode lets a test make the "model" fail, hang or be slow.
      if (fakeMode === "error") {
        res.statusCode = 500;
        res.end('{"error":{"message":"upstream exploded"}}');
      } else if (fakeMode === "hang") setTimeout(reply, 6_000);
      else if (fakeMode === "slow") setTimeout(reply, 3_000);
      else reply();
    });
  });
  await new Promise((r) => fake.listen(0, "127.0.0.1", r));
  const fakeUrl = `http://127.0.0.1:${fake.address().port}/v1beta/interactions`;

  // Backend from a temp copy, with seed-01 opened for Try.
  tmp = await mkdtemp(join(tmpdir(), "mosaic-e2e-"));
  for (const dir of ["app", "data", "storage"])
    await cp(join(ROOT, "apps/backend", dir), join(tmp, dir), {
      recursive: true,
    });
  const recipesPath = join(tmp, "data/recipes.json");
  const recipes = JSON.parse(await readFile(recipesPath, "utf8"));
  recipes[0].tryReady = true;
  await writeFile(recipesPath, JSON.stringify(recipes));
  const apiPort = await freePort();
  const api = spawn(
    PYTHON,
    [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(apiPort),
    ],
    {
      cwd: tmp,
      stdio: "ignore",
      detached: true,
      env: {
        ...process.env,
        GEMINI_API_KEY: "e2e-key",
        MOSAIC_PROVIDER_ENDPOINT: fakeUrl,
        MOSAIC_PROVIDER_TIMEOUT: "4",
        // Generous per-visitor limits: these tests are all one "visitor".
        // The limits themselves are covered by apps/backend/tests/test_limits.py.
        MOSAIC_RATE_PER_MINUTE: "100",
        MOSAIC_DAILY_PER_CLIENT: "100",
        BLOB_READ_WRITE_TOKEN: "",
        BLOB_STORE_ID: "",
        VERCEL: "",
      },
    },
  );
  children.push(api);
  await waitFor(`http://127.0.0.1:${apiPort}/api/health`, 20_000, api);

  // Website (dev server, so no build directory is touched).
  const webPort = await freePort();
  // localhost, not 127.0.0.1: Next dev blocks its client scripts for other origins.
  web = `http://localhost:${webPort}`;
  const next = spawn(
    "pnpm",
    [
      "--filter",
      "@mosaic/web",
      "exec",
      "next",
      "dev",
      "--webpack",
      "-p",
      String(webPort),
    ],
    {
      cwd: ROOT,
      stdio: "ignore",
      detached: true,
      env: {
        ...process.env,
        BACKEND_URL: `http://127.0.0.1:${apiPort}`,
        PORT: "",
      },
    },
  );
  children.push(next);
  await waitFor(`${web}/api/health`, 120_000, next);
  browser = await chromium.launch();
});

after(async () => {
  await browser?.close();
  for (const c of children) {
    try {
      process.kill(-c.pid); // whole process group (pnpm -> next -> next-server)
    } catch {
      c.kill();
    }
  }
  fake?.close();
  if (tmp) await rm(tmp, { recursive: true, force: true });
});

async function page(viewport = { width: 1280, height: 800 }) {
  const ctx = await browser.newContext({ viewport });
  const p = await ctx.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  p.errors = errors;
  return p;
}

test(
  "discover → recipe → create → live result → refresh → favorites",
  { timeout: 180_000 },
  async () => {
    const p = await page();
    await p.goto(web + "/");
    await p.waitForSelector(".recipe-card");
    assert.equal(await p.locator(".recipe-card").count(), 3);
    assert.equal(
      await p.locator(".recipe-card", { hasText: "來源待確認" }).count(),
      3,
    );

    // Category filter narrows the list.
    await p.getByRole("button", { name: "Paper Cut" }).click();
    assert.equal(await p.locator(".recipe-card").count(), 1);
    await p.getByRole("button", { name: "All" }).click();

    // Recipe page: public prompt, source link, no unverified IG link.
    await p.locator(".recipe-card a", { hasText: "Geometric" }).click();
    await p.waitForSelector(".prompt-text");
    assert.match(
      await p.locator(".prompt-text").innerText(),
      /geometric, modular illustration/,
    );
    const source = p.getByRole("link", { name: "查看原始貼文" }).first();
    assert.equal(
      await source.getAttribute("href"),
      "https://www.threads.com/share/_g9YMjJ1V/",
    );
    assert.equal(
      await p.getByRole("link", { name: "前往原作者 IG" }).count(),
      0,
    );
    await p.getByRole("button", { name: "Save to Favorites" }).click();

    // Create: live mode, so no demo-mode notice.
    await p.getByRole("link", { name: "TRY THIS RECIPE" }).click();
    await p.waitForSelector(".upload-area");
    await p.waitForTimeout(500);
    assert.equal(await p.locator(".mode-notice").count(), 0);
    // Client-side validation rejects a non-image.
    await p.setInputFiles("#image-upload", {
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("hi"),
    });
    await p.getByText("只支援 JPEG / PNG / WebP").waitFor();
    await p.setInputFiles("#image-upload", {
      name: "me.png",
      mimeType: "image/png",
      buffer: PNG,
    });
    await p.getByAltText("你選擇的照片").waitFor();
    await p.getByRole("button", { name: "CREATE" }).click();

    // Result: live image, verbatim disclosure, attribution, next steps.
    await p.waitForURL(/\/result\/[0-9a-f]{32}$/);
    await p.waitForSelector(".disclosure-live");
    assert.match(await p.locator(".disclosure").innerText(), /即時生成/);
    const img = p.locator(".result-image img");
    await img.waitFor();
    assert.ok(await img.evaluate((el) => el.complete && el.naturalWidth === 2));
    assert.ok(await p.getByRole("link", { name: "再試一次" }).isVisible());
    assert.ok(await p.getByRole("link", { name: "返回 Recipe" }).isVisible());
    assert.ok(await p.getByRole("button", { name: "Download" }).isEnabled());

    // The model got the stored prompt, the photo, the key and the 3:4 ratio.
    const call = modelCalls.at(-1);
    assert.equal(call.key, "e2e-key");
    assert.match(
      call.body.input[0].text,
      /^Create a separate, high-end design poster/,
    );
    assert.equal(
      Buffer.from(call.body.input[1].data, "base64").equals(PNG),
      true,
    );
    assert.equal(call.body.response_format.aspect_ratio, "3:4");

    // Refresh keeps the same result.
    const url = p.url();
    await p.reload();
    await p.waitForSelector(".disclosure-live");
    assert.equal(p.url(), url);

    // Favorites survive navigation on this device.
    await p.goto(web + "/my-recipes");
    await p.waitForSelector(".recipe-card");
    assert.equal(await p.locator(".recipe-card").count(), 1);
    assert.deepEqual(p.errors, []);
  },
);

test(
  "recipes not yet verified cannot be tried, even by direct URL",
  { timeout: 60_000 },
  async () => {
    const p = await page();
    await p.goto(web + "/recipe/seed-02");
    await p.waitForSelector(".prompt-text");
    assert.ok(
      await p.getByRole("button", { name: "尚未開放試用" }).isDisabled(),
    );
    await p.goto(web + "/create/seed-02");
    await p.waitForSelector(".upload-area");
    assert.ok(await p.locator(".upload-area").isDisabled());
    assert.ok(
      await p.getByRole("button", { name: "尚未開放試用" }).isDisabled(),
    );
  },
);

test(
  "demo mode is announced before uploading when no model key is set",
  { timeout: 60_000 },
  async () => {
    const p = await page();
    await p.route("**/api/health", (r) =>
      r.fulfill({ json: { ok: true, liveGeneration: false } }),
    );
    await p.goto(web + "/create/seed-01");
    await p.locator(".mode-notice").waitFor();
    assert.match(await p.locator(".mode-notice").innerText(), /示範模式/);
  },
);

test(
  "missing recipe and result show clear errors",
  { timeout: 60_000 },
  async () => {
    const p = await page();
    await p.goto(web + "/recipe/seed-99");
    await p.getByText("找不到這份 recipe").waitFor();
    await p.goto(web + "/result/" + "0".repeat(32));
    await p.getByText("結果不存在或連結已失效").waitFor();
    await p.goto(web + "/no-such-page");
    await p.getByText("找不到這個頁面").waitFor();
  },
);

test(
  "every page fits a 390px phone screen without sideways scrolling",
  { timeout: 120_000 },
  async () => {
    const p = await page({ width: 390, height: 844 });
    for (const path of [
      "/",
      "/recipe/seed-01",
      "/create/seed-01",
      "/my-recipes",
      "/about",
    ]) {
      await p.goto(web + path);
      // Wait until data has loaded (no "載入中…" placeholder left).
      await p.locator("main").waitFor();
      await p.waitForFunction(
        () => !document.body.innerText.includes("載入中"),
      );
      const overflow = await p.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      );
      assert.ok(overflow <= 0, `${path} overflows by ${overflow}px`);
    }
  },
);

// Shared helper: open Create for seed-01 and pick a photo.
async function openCreate(
  p,
  file = { name: "me.png", mimeType: "image/png", buffer: PNG },
) {
  await p.goto(web + "/create/seed-01");
  await p.waitForSelector(".upload-area:not([disabled])");
  await p.setInputFiles("#image-upload", file);
  await p.getByAltText("你選擇的照片").waitFor();
}

function uniquePng(seed) {
  // Same 2x2 image with a different trailing chunk -> a different photo hash.
  const end = PNG.length - 12; // before IEND
  const text = Buffer.from(`tEXtk\0${seed}`);
  const len = Buffer.alloc(4);
  len.writeUInt32BE(text.length - 4);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(text));
  return Buffer.concat([
    PNG.subarray(0, end),
    len,
    text,
    crc,
    PNG.subarray(end),
  ]);
}

test(
  "download, explore more, and a double click pays once",
  { timeout: 120_000 },
  async () => {
    fakeMode = "slow";
    const p = await page();
    await openCreate(p, {
      name: "dbl.png",
      mimeType: "image/png",
      buffer: uniquePng("dbl"),
    });
    const before = modelCalls.length;
    const create = p.getByRole("button", { name: "CREATE" });
    await create.dblclick();
    await p.getByText("CREATING…").waitFor();
    assert.ok(await p.getByRole("button", { name: "CREATING…" }).isDisabled());
    await p.waitForURL(/\/result\//, { timeout: 30_000 });
    fakeMode = "ok";
    assert.equal(
      modelCalls.length - before,
      1,
      "one model call for a double click",
    );

    const [download] = await Promise.all([
      p.waitForEvent("download"),
      p.getByRole("button", { name: "Download" }).click(),
    ]);
    assert.match(download.suggestedFilename(), /^mosaic-[0-9a-f]{32}\.png$/);

    await p.getByRole("link", { name: "EXPLORE MORE RECIPES" }).click();
    await p.waitForSelector(".recipe-card");
    assert.equal(new URL(p.url()).pathname, "/");
  },
);

test(
  "model errors and timeouts end in an honest fallback, not a fake image",
  { timeout: 120_000 },
  async () => {
    for (const mode of ["error", "hang"]) {
      fakeMode = mode;
      const p = await page();
      await openCreate(p, {
        name: `${mode}.png`,
        mimeType: "image/png",
        buffer: uniquePng(mode),
      });
      await p.getByRole("button", { name: "CREATE" }).click();
      await p.waitForURL(/\/result\//, { timeout: 30_000 });
      await p.waitForSelector(".disclosure");
      // No cached example exists for seed-01, so the result is the labelled placeholder.
      assert.equal(await p.locator(".disclosure-live").count(), 0, mode);
      assert.equal(await p.locator(".result-image img").count(), 0, mode);
      assert.ok(
        await p.getByRole("button", { name: "Download" }).isDisabled(),
        mode,
      );
    }
    fakeMode = "ok";
  },
);

test(
  "refreshing during generation and trying again does not pay twice",
  { timeout: 120_000 },
  async () => {
    fakeMode = "slow";
    const photo = {
      name: "refresh.png",
      mimeType: "image/png",
      buffer: uniquePng("refresh"),
    };
    const p = await page();
    const before = modelCalls.length;
    await openCreate(p, photo);
    await p.getByRole("button", { name: "CREATE" }).click();
    await p.getByText("CREATING…").waitFor();
    await p.reload(); // the in-flight request finishes on the server anyway
    await p.waitForTimeout(3_500);
    await openCreate(p, photo);
    await p.getByRole("button", { name: "CREATE" }).click();
    await p.waitForURL(/\/result\//, { timeout: 30_000 });
    fakeMode = "ok";
    assert.equal(modelCalls.length - before, 1);
  },
);

test(
  "limits, oversized and invalid files show clear messages",
  { timeout: 120_000 },
  async () => {
    const p = await page();
    // Over 8MB is refused in the browser before upload.
    await p.goto(web + "/create/seed-01");
    await p.waitForSelector(".upload-area:not([disabled])");
    await p.setInputFiles("#image-upload", {
      name: "huge.png",
      mimeType: "image/png",
      buffer: Buffer.alloc(8 * 1024 * 1024 + 1),
    });
    await p.getByText("照片請小於 8MB").waitFor();

    // A file that claims to be a PNG but is not one is refused by the server.
    await openCreate(p, {
      name: "fake.png",
      mimeType: "image/png",
      buffer: Buffer.from("not an image"),
    });
    await p.getByRole("button", { name: "CREATE" }).click();
    await p.getByText("只支援 JPEG / PNG / WebP").waitFor();

    // Server-side limits, as the server would answer them.
    for (const [status, error, message] of [
      [429, "rate_limited", "操作太頻繁了"],
      [429, "daily_limit_reached", "今天的免費生成次數已用完"],
      [503, "daily_budget_reached", "今天的生成額度已用完"],
    ]) {
      await p.route("**/api/generate", (r) =>
        r.fulfill({ status, json: { error } }),
      );
      await openCreate(p, {
        name: "x.png",
        mimeType: "image/png",
        buffer: uniquePng(error),
      });
      await p.getByRole("button", { name: "CREATE" }).click();
      await p.getByText(message).waitFor();
      await p.unroute("**/api/generate");
    }
  },
);

test(
  "a 4–8MB photo is shrunk in the browser to fit hosting limits",
  { timeout: 120_000 },
  async () => {
    const big = join(tmp, "big.png");
    const made = spawn(PYTHON, [
      "-c",
      "import os,sys; from PIL import Image; Image.frombytes('RGB',(1400,1300),os.urandom(1400*1300*3)).save(sys.argv[1])",
      big,
    ]);
    await new Promise((r) => made.on("exit", r));
    const bytes = await readFile(big);
    assert.ok(
      bytes.length > 4 * 1024 * 1024 && bytes.length < 8 * 1024 * 1024,
      `${bytes.length}`,
    );
    const p = await page();
    const before = modelCalls.length;
    await openCreate(p, {
      name: "big.png",
      mimeType: "image/png",
      buffer: bytes,
    });
    await p.getByRole("button", { name: "CREATE" }).click();
    await p.waitForURL(/\/result\//, { timeout: 30_000 });
    const sent = modelCalls.slice(before)[0].body.input[1];
    assert.equal(sent.mime_type, "image/jpeg");
    assert.ok(Buffer.from(sent.data, "base64").length <= 4 * 1024 * 1024);
  },
);
