/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      {
        source: "/training",
        destination: "/guide",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
