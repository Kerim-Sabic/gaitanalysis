/** @type {import('next').NextConfig} */

// Explicit backend URL (set on Netlify / self-host). In production the web client
// calls this absolute URL directly, so NO localhost is referenced in the bundle.
const EXPLICIT_API_TARGET = (
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  ""
).replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  // Compile the shared TS package (imported as source, not pre-built).
  transpilePackages: ["@horalix/shared"],
  async rewrites() {
    // Same-origin "/api/*" proxy so local `npm run dev` works with zero config.
    // The localhost fallback is DEVELOPMENT-ONLY (gated by NODE_ENV); a Netlify
    // production build references no localhost and uses NEXT_PUBLIC_API_URL.
    const isDev = process.env.NODE_ENV !== "production";
    const target = EXPLICIT_API_TARGET || (isDev ? "http://localhost:8000" : "");
    if (!target) return [];
    return [{ source: "/api/:path*", destination: `${target}/:path*` }];
  },
};

export default nextConfig;
