/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
  eslint: {
    // @typescript-eslint plugin is not in deps; TypeScript compiler still runs strict type checking.
    ignoreDuringBuilds: true,
  },
  // deck.gl 9 and its dependencies ship as ESM modules.
  // Next.js requires these to be transpiled by webpack.
  transpilePackages: [
    'deck.gl',
    '@deck.gl/core',
    '@deck.gl/react',
    '@deck.gl/layers',
    '@deck.gl/geo-layers',
    '@deck.gl/mesh-layers',
    '@luma.gl/core',
    '@luma.gl/webgl',
    '@luma.gl/shadertools',
    '@math.gl/core',
    '@math.gl/web-mercator',
    '@probe.gl/log',
    '@probe.gl/stats',
  ],
}

module.exports = nextConfig
