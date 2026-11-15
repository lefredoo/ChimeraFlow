import type { NextConfig } from "next";

// Local config on purpose: Next.js searches parent directories for a config file,
// so an explicit one keeps the build independent of files outside the repository.
const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
