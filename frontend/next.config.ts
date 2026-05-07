import type { NextConfig } from "next";
import dns from "node:dns";

dns.setDefaultResultOrder("ipv4first");
const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/backend-api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;