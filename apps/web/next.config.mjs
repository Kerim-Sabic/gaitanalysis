/** @type {import('next').NextConfig} */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Compile the shared TS package (imported as source, not pre-built).
  transpilePackages: ["@horalix/shared"],
  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the browser hits one origin.
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
