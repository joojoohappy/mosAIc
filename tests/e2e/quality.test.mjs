// Accessibility, broken links and load performance on a production build.
//
//   pnpm test:e2e
//
// Builds the website into .next-quality (so a normal build is left alone),
// serves it with `next start` against a local backend with no model key, and
// checks every page:
//   - axe-core: no serious or critical accessibility violations
//   - every internal link answers 200
//   - load timings and JavaScript size stay within a local budget
// External links (Threads, Instagram, GitHub) are listed, not fetched: they
// depend on third-party sites and on this machine's network.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";

const ROOT = new URL("../..", import.meta.url).pathname;
const PYTHON = join(ROOT, "apps/backend/.venv/bin/python");
const AXE = await readFile(
  createRequire(import.meta.url).resolve("axe-core/axe.min.js"),
  "utf8",
);
// Local budget: generous for a laptop/CI box, tight enough to catch a regression.
const BUDGET = { lcpMs: 2500, jsKb: 400 };
const children = [];
let tmp, web, browser, resultId;

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
  tmp = await mkdtemp(join(tmpdir(), "mosaic-quality-"));
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
    ["-m", "uvicorn", "app.main:app", "--port", String(apiPort)],
    {
      cwd: tmp,
      stdio: "ignore",
      detached: true,
      env: {
        ...process.env,
        GEMINI_API_KEY: "",
        BLOB_READ_WRITE_TOKEN: "",
        BLOB_STORE_ID: "",
        VERCEL: "",
      },
    },
  );
  children.push(api);
  await waitFor(`http://127.0.0.1:${apiPort}/api/health`, 20_000, api);

  const env = {
    ...process.env,
    BACKEND_URL: `http://127.0.0.1:${apiPort}`,
    MOSAIC_DIST_DIR: ".next-quality",
    PORT: "",
  };
  const build = spawnSync(
    "pnpm",
    ["--filter", "@mosaic/web", "exec", "next", "build"],
    { cwd: ROOT, env, encoding: "utf8" },
  );
  assert.equal(build.status, 0, build.stdout + build.stderr);
  console.log(
    build.stdout
      .split("\n")
      .filter((l) => /^[┌├└│○ƒ]/.test(l.trim()))
      .join("\n"),
  );

  const webPort = await freePort();
  web = `http://localhost:${webPort}`;
  const server = spawn(
    "pnpm",
    ["--filter", "@mosaic/web", "exec", "next", "start", "-p", String(webPort)],
    { cwd: ROOT, stdio: "ignore", detached: true, env },
  );
  children.push(server);
  await waitFor(`${web}/api/health`, 60_000, server);

  // One stored (mock) result so the result page has something to show.
  const photo = spawnSync(
    PYTHON,
    [
      "-c",
      "import sys,io; from PIL import Image; b=io.BytesIO(); Image.new('RGB',(64,48),(20,90,160)).save(b,'JPEG'); sys.stdout.buffer.write(b.getvalue())",
    ],
    { encoding: "buffer" },
  ).stdout;
  const form = new FormData();
  form.set("recipeId", "seed-01");
  form.set("image", new Blob([photo], { type: "image/jpeg" }), "p.jpg");
  const res = await fetch(`${web}/api/generate`, {
    method: "POST",
    body: form,
  });
  resultId = (await res.json()).resultId;
  assert.match(resultId, /^[0-9a-f]{32}$/);
  browser = await chromium.launch();
});

after(async () => {
  await browser?.close();
  for (const c of children) {
    try {
      process.kill(-c.pid);
    } catch {
      c.kill();
    }
  }
  if (tmp) await rm(tmp, { recursive: true, force: true });
  await rm(join(ROOT, "apps/web/.next-quality"), {
    recursive: true,
    force: true,
  });
});

const pages = () => [
  "/",
  "/recipe/seed-01",
  "/recipe/seed-02",
  "/create/seed-01",
  "/create/seed-02",
  `/result/${resultId}`,
  "/my-recipes",
  "/about",
  "/privacy",
  "/terms",
  "/recipe/seed-99",
  "/no-such-page",
];

async function open(path, viewport) {
  const ctx = await browser.newContext({ viewport });
  const p = await ctx.newPage();
  await p.goto(web + path, { waitUntil: "load" });
  await p
    .getByText("載入中")
    .first()
    .waitFor({ state: "detached", timeout: 15_000 })
    .catch(() => {});
  return { p, ctx };
}

test("no serious accessibility problems on any page (desktop and phone)", async () => {
  const problems = [];
  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 390, height: 844 },
  ]) {
    for (const path of pages()) {
      const { p, ctx } = await open(path, viewport);
      await p.addScriptTag({ content: AXE });
      const found = await p.evaluate(async () => {
        const r = await window.axe.run(document, {
          runOnly: [
            "wcag2a",
            "wcag2aa",
            "wcag21a",
            "wcag21aa",
            "best-practice",
          ],
        });
        return r.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          nodes: v.nodes.length,
          sample: v.nodes[0]?.target.join(" "),
          // Every element, with the measured contrast where that applies.
          detail: v.nodes.map((n) => {
            const d = n.any[0]?.data;
            return d?.contrastRatio
              ? `${n.target.join(" ")} ${d.fgColor} on ${d.bgColor} = ${d.contrastRatio}:1`
              : n.target.join(" ");
          }),
        }));
      });
      for (const v of found)
        console.log(
          `  axe ${viewport.width}px ${path}: ${v.impact} ${v.id} ×${v.nodes}\n      ${v.detail.join("\n      ")}`,
        );
      problems.push(
        ...found
          .filter((v) => v.impact === "serious" || v.impact === "critical")
          .map((v) => `${viewport.width}px ${path}: ${v.id} (${v.sample})`),
      );
      await ctx.close();
    }
  }
  assert.deepEqual(problems, []);
});

test("every internal link works; external links are listed", async () => {
  const internal = new Set();
  const external = new Set();
  for (const path of pages()) {
    const { p, ctx } = await open(path, { width: 1280, height: 800 });
    const hrefs = await p.$$eval("a[href]", (as) => as.map((a) => a.href));
    for (const h of hrefs) {
      const u = new URL(h);
      if (u.origin === new URL(web).origin) internal.add(u.pathname);
      else if (/^https?:$/.test(u.protocol)) external.add(u.href);
    }
    await ctx.close();
  }
  const broken = [];
  for (const path of internal) {
    const r = await fetch(web + path);
    if (r.status !== 200) broken.push(`${path} → ${r.status}`);
  }
  console.log(`  internal links checked: ${[...internal].sort().join(", ")}`);
  console.log(
    `  external links (not fetched): ${[...external].sort().join(", ")}`,
  );
  assert.deepEqual(broken, []);
  for (const h of external) assert.match(h, /^https:\/\//, `${h} is not https`);
});

test("pages load within the local performance budget", async () => {
  const rows = [];
  for (const path of pages()) {
    const { p, ctx } = await open(path, { width: 1280, height: 800 });
    const m = await p.evaluate(
      () =>
        new Promise((resolve) => {
          let lcp = 0;
          new PerformanceObserver((l) => {
            for (const e of l.getEntries()) lcp = Math.max(lcp, e.startTime);
          }).observe({ type: "largest-contentful-paint", buffered: true });
          setTimeout(() => {
            const nav = performance.getEntriesByType("navigation")[0];
            const js = performance
              .getEntriesByType("resource")
              .filter((r) => r.initiatorType === "script")
              .reduce((n, r) => n + r.transferSize, 0);
            resolve({
              ttfb: Math.round(nav.responseStart),
              dcl: Math.round(nav.domContentLoadedEventEnd),
              lcp: Math.round(lcp),
              jsKb: Math.round(js / 1024),
            });
          }, 500);
        }),
    );
    rows.push({ path: path.replace(resultId, "<id>"), ...m });
    await ctx.close();
  }
  console.table(rows);
  const over = rows.filter((r) => r.lcp > BUDGET.lcpMs || r.jsKb > BUDGET.jsKb);
  assert.deepEqual(over, []);
});
