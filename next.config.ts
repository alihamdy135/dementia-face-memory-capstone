import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["mongodb"],
  poweredByHeader: false,
};

export default nextConfig;
