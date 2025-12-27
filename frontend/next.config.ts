import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://backend:8000/api/:path*",
      },
      {
        source: "/ws/:path*",
        destination: "http://backend:8000/ws/:path*",
      },
      {
        source: "/data/:path*",
        destination: "http://backend:8000/data/:path*",
      },
    ];
  },
  experimental: {
    serverActions: {
      bodySizeLimit: "250mb",
    },
  },
};

export default nextConfig;
