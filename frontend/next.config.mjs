/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  // No "X-Powered-By: Next.js": the framework and its version are nobody's business.
  poweredByHeader: false,
  async headers() {
    // The service worker must never be served from a cache, or a fixed bug could
    // keep running on people's phones. It also may not widen its own scope.
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
  async rewrites() {
    // Lets the browser call /api/* on the same origin during dev; proxied to FastAPI.
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
