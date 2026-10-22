// Closed-loop HTTP load generator (zero dependencies; Node >= 22 built-in fetch/undici).
// N workers each send requests back-to-back; latency = time to full response body.
//
//   node benchmarks/loadgen.mjs --url http://127.0.0.1:8100/api/recipes \
//        --concurrency 8 --requests 2000 --warmup 200 --out benchmarks/raw/x.json
//   POST multipart:  --method POST --form recipeId=seed-01 --file image=path.png
//
// Notes for readers: closed-loop generators under-report tail latency when the
// server stalls (coordinated omission). That is acceptable here because every
// scenario reports throughput alongside latency and none claims an SLO.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; };
const all = (k) => argv.flatMap((a, i) => (a === `--${k}` ? [argv[i + 1]] : []));
const url = opt("url"), method = opt("method", "GET");
const concurrency = +opt("concurrency", 1), total = +opt("requests", 100), warmup = +opt("warmup", 0);
const out = opt("out"), label = opt("label", "");
const forms = all("form").map((s) => s.split("=", 2));
const files = all("file").map((s) => { const [k, p] = s.split("=", 2); return [k, p, fs.readFileSync(p)]; });

function body() {
  if (!forms.length && !files.length) return undefined;
  const fd = new FormData();
  for (const [k, v] of forms) fd.append(k, v);
  for (const [k, p, buf] of files) fd.append(k, new Blob([buf], { type: "image/png" }), path.basename(p));
  return fd;
}

async function one() {
  const t0 = performance.now();
  try {
    const r = await fetch(url, { method, body: body(), signal: AbortSignal.timeout(+opt("timeout-ms", 120000)) });
    await r.arrayBuffer();
    return [performance.now() - t0, r.status];
  } catch (e) {
    return [performance.now() - t0, 0, String(e.cause?.code || e.name)];
  }
}

async function phase(n) {
  const samples = [];
  let next = 0;
  const workers = Array.from({ length: concurrency }, async () => {
    while (next < n) { next++; samples.push(await one()); }
  });
  const t0 = performance.now();
  await Promise.all(workers);
  return { samples, wallMs: performance.now() - t0 };
}

if (warmup) await phase(warmup);
const { samples, wallMs } = await phase(total);
const lat = samples.map((s) => s[0]).sort((a, b) => a - b);
const q = (p) => lat[Math.min(lat.length - 1, Math.floor((p / 100) * lat.length))];
const statuses = {};
for (const s of samples) statuses[s[2] || s[1]] = (statuses[s[2] || s[1]] || 0) + 1;
const summary = {
  label, url, method, concurrency, requests: total, warmup,
  wallMs: +wallMs.toFixed(1), rps: +((total / wallMs) * 1000).toFixed(1),
  p50: +q(50).toFixed(2), p95: +q(95).toFixed(2), p99: +q(99).toFixed(2), max: +lat.at(-1).toFixed(2),
  mean: +(lat.reduce((a, b) => a + b, 0) / lat.length).toFixed(2), statuses,
  env: { node: process.version, cpus: os.cpus().length, cpu: os.cpus()[0].model, platform: `${os.platform()}-${os.arch()}` },
};
if (out) {
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify({ summary, samples }, null, 0));
}
console.log(JSON.stringify(summary));
