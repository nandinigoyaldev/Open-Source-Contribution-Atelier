/**
 * Next.js configuration for SSR/SSG.
 * 
 * @file next.config.js
 * @location frontend/next.config.js
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode
  reactStrictMode: true,

  // Enable SWC for faster builds
  swcMinify: true,

  // Image optimization
  images: {
    domains: ['localhost', 'api.github.com', 'avatars.githubusercontent.com'],
    formats: ['image/avif', 'image/webp'],
  },

  // Compiler options
  compiler: {
    // Remove console.log in production
    removeConsole: process.env.NODE_ENV === 'production',
  },

  // Experimental features
  experimental: {
    // Enable server actions
    serverActions: true,
  },

  // Environment variables available to the client
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_GA_MEASUREMENT_ID: process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID,
  },

  // Redirects
  async redirects() {
    return [
      {
        source: '/old-dashboard',
        destination: '/dashboard',
        permanent: true,
      },
      {
        source: '/old-lesson/:path*',
        destination: '/learn/:path*',
        permanent: true,
      },
    ];
  },

  // Headers for security
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
      {
        source: '/_next/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;