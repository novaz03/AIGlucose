// next.config.mjs
/** @type {import('next').NextConfig} */

const isProd =
  process.env.VERCEL_ENV === 'production' ||
  process.env.NODE_ENV === 'production';

const backendOrigin =
  process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:2467';

const nextConfig = {
  reactStrictMode: true,

  // Safer defaults: ignore TS/ESLint only on non-production builds
  typescript: {
    ignoreBuildErrors: !isProd,
  },
  eslint: {
    ignoreDuringBuilds: !isProd,
  },

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },

  // Add/keep any other settings here:
  // output: 'standalone',
  // images: { domains: ['...'] },
  // experimental: { ppr: true },
};

export default nextConfig;
