// apps/web/proxy.ts: the website tells the API who the visitor is, and a
// browser cannot forge that.
import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { createRequire, registerHooks } from "node:module";

// Next resolves the extensionless "next/server" with its bundler; plain Node
// needs the file name.
registerHooks({
  resolve: (spec, ctx, next) =>
    next(spec === "next/server" ? "next/server.js" : spec, ctx),
});
const { proxy, config } = await import("../apps/web/proxy.ts");

const { NextRequest } = createRequire(
  new URL("../apps/web/package.json", import.meta.url),
)("next/server");

const saved = { ...process.env };
afterEach(() => {
  for (const k of ["VERCEL", "MOSAIC_PROXY_SECRET", "MOSAIC_TRUST_X_REAL_IP"]) {
    if (k in saved) process.env[k] = saved[k];
    else delete process.env[k];
  }
});

// Headers the proxy hands to the rewrite destination (the API).
function forwarded(headers, env) {
  Object.assign(process.env, env);
  const res = proxy(
    new NextRequest("https://site.example/api/generate", {
      method: "POST",
      headers,
    }),
  );
  const out = {};
  for (const [k, v] of res.headers) {
    if (k.startsWith("x-middleware-request-"))
      out[k.slice("x-middleware-request-".length)] = v;
  }
  return out;
}

test("only runs for generate requests", () => {
  assert.equal(config.matcher, "/api/generate");
});

test("on Vercel, signs the platform's x-real-ip for the API", () => {
  const h = forwarded(
    { "x-real-ip": "203.0.113.7", "x-forwarded-for": "1.1.1.1" },
    { VERCEL: "1", MOSAIC_PROXY_SECRET: "s3cret" },
  );
  assert.equal(h["x-mosaic-client-ip"], "203.0.113.7");
  assert.equal(h["x-mosaic-proxy-secret"], "s3cret");
});

test("drops forged headers from the browser", () => {
  const forged = {
    "x-mosaic-client-ip": "6.6.6.6",
    "x-mosaic-proxy-secret": "guess",
  };
  // Not on a platform that sets x-real-ip: nothing is vouched for.
  const h = forwarded(
    { ...forged, "x-real-ip": "6.6.6.6" },
    { VERCEL: "", MOSAIC_TRUST_X_REAL_IP: "", MOSAIC_PROXY_SECRET: "s3cret" },
  );
  assert.equal(h["x-mosaic-client-ip"], undefined);
  assert.equal(h["x-mosaic-proxy-secret"], undefined);
  // No secret configured: nothing is vouched for either.
  const h2 = forwarded(
    { ...forged, "x-real-ip": "6.6.6.6" },
    { VERCEL: "1", MOSAIC_PROXY_SECRET: "" },
  );
  assert.equal(h2["x-mosaic-client-ip"], undefined);
});
