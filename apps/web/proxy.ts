import { NextResponse, type NextRequest } from "next/server";

// Tells the API which visitor sent a generate request, so per-visitor limits
// count real people instead of whatever X-Forwarded-For a client makes up.
//
// The visitor IP is only taken from a header the hosting platform sets itself
// (x-real-ip on Vercel, or behind your own reverse proxy with
// MOSAIC_TRUST_X_REAL_IP=1). It is signed with MOSAIC_PROXY_SECRET, which the
// API checks before trusting it. Headers with these names sent by a browser
// are always dropped.
export function proxy(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.delete("x-mosaic-client-ip");
  headers.delete("x-mosaic-proxy-secret");

  const secret = process.env.MOSAIC_PROXY_SECRET;
  const platformSetsRealIp =
    !!process.env.VERCEL || process.env.MOSAIC_TRUST_X_REAL_IP === "1";
  const ip = platformSetsRealIp
    ? request.headers.get("x-real-ip")?.trim().slice(0, 64)
    : undefined;
  if (secret && ip) {
    headers.set("x-mosaic-client-ip", ip);
    headers.set("x-mosaic-proxy-secret", secret);
  }
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: "/api/generate" };
