import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // The agent may push NASA public-domain archive images; nothing else.
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images-assets.nasa.gov",
        pathname: "/image/**",
      },
    ],
  },
};

export default nextConfig;
