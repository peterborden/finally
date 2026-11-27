/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: FastAPI serves the emitted `out/` directory as the SPA.
  output: 'export',
  // No Next image optimization server in a static export.
  images: { unoptimized: true },
  trailingSlash: false,
  reactStrictMode: true,
};

export default nextConfig;
