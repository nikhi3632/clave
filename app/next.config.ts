import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: "dist",
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
};

export default nextConfig;
