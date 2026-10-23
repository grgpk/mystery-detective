import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The dev server only trusts `localhost` by default; opening the game at 127.0.0.1 would otherwise block the
  // hot-reload socket and dev assets, leaving the page stuck retrying its WebSocket.
  allowedDevOrigins: ["127.0.0.1"],
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
