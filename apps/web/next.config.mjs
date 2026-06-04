/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Compile the shared TS package (imported as source, not pre-built).
  transpilePackages: ["@horalix/shared"],
};

export default nextConfig;
