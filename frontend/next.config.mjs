/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  // No "X-Powered-By: Next.js": the framework and its version are nobody's business.
  poweredByHeader: false,
  async rewrites() {
    // Lets the browser call /api/* on the same origin during dev; proxied to FastAPI.
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
