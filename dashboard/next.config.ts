import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: '/orchestrator-api/:path*',
        destination: 'http://orchestrator:9000/:path*'
      },
      {
        source: '/api/node-a/:path*',
        // Hardcoded docker internal network names for nodes
        destination: 'http://node-a:8000/:path*'
      },
      {
        source: '/api/node-b/:path*',
        destination: 'http://node-b:8000/:path*'
      }
    ]
  }
};

export default nextConfig;
