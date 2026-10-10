import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  // Use the compiler API so builds remain reliable on Node versions where
  // child-process stdout can close before `tsc --showConfig` is fully read.
  experimental: { useTypeScriptCli: false },
};

export default nextConfig;
