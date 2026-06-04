/** @type {import('next').NextConfig} */

// Local dev / self-host proxy target. On Netlify the browser uses
// NEXT_PUBLIC_API_URL directly (absolute) and this rewrite is not relied upon.
const API_PROXY_TARGET = (
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  // Compile the shared TS package (imported as source, not pre-built).
  transpilePackages: ["@horalix/shared"],
  async rewrites() {
    // Same-origin proxy so the web client can call "/api/*" with zero config.
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/:path*` }];
  },
};

export default nextConfig;
