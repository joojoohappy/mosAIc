import type { NextConfig } from "next";
const backend = new URL(process.env.BACKEND_URL || "http://127.0.0.1:8000");
if (
  !["http:", "https:"].includes(backend.protocol) ||
  backend.username ||
  backend.password ||
  backend.pathname !== "/" ||
  backend.search ||
  backend.hash
)
  throw new Error(
    "BACKEND_URL must be an HTTP(S) origin without credentials or a path.",
  );
const nextConfig: NextConfig = {
  transpilePackages: [
    "@mosaic/api",
    "@mosaic/types",
    "@mosaic/core",
    "@mosaic/design",
  ],
  poweredByHeader: false,
  experimental: {
    proxyTimeout: 75_000,
    useTypeScriptCli: false,
    ...(process.env.MOSAIC_BUILD_WORKERS === "threads"
      ? { workerThreads: true, webpackBuildWorker: false, cpus: 2 }
      : {}),
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend.origin}/api/:path*` },
      {
        source: "/static/:path*",
        destination: `${backend.origin}/static/:path*`,
      },
    ];
  },
};
export default nextConfig;
