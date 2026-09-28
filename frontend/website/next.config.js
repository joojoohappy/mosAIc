/** @type {import('next').NextConfig} */
// FastAPI (localhost:8000) is the only API owner. These rewrites make it same-origin,
// so there is no CORS and the frontend codes against /api/* exactly as documented.
//
// Rewrites run afterFiles: any real file under app/api/ WINS over the proxy and the
// request never reaches Python. That is why app/api/generate/route.ts was removed —
// with it present, POST /api/generate returns 405 instead of proxying.
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' },
      { source: '/static/:path*', destination: 'http://localhost:8000/static/:path*' },
    ];
  },
};

module.exports = nextConfig;
