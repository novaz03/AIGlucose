// next.config.mjs
/** @type {import('next').NextConfig} */
const backendOrigin = process.env.BACKEND_ORIGIN ?? 'http://34.66.204.223:2467';

const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${backendOrigin}/api/:path*` },
    ];
  },
};

export default nextConfig;
