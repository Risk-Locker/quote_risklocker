/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  typedRoutes: true,
  async redirects() {
    return [
      {
        source: "/builder",
        destination: "/builder/templates/quotation-templates",
        permanent: false,
      },
      {
        source: "/builder/templates",
        destination: "/builder/templates/quotation-templates",
        permanent: false,
      },
      {
        source: "/builder/templates/benefit-templates",
        destination: "/builder/templates/quotation-templates",
        permanent: false,
      },
      {
        source: "/builder/templates/:id/builder",
        destination: "/builder/templates/quotation-templates",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
