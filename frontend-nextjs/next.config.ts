import type { NextConfig } from "next";

const config: NextConfig = {
  // Serveur autonome (.next/standalone) : c'est ce paquet que le workflow déploie sur App Service (Node).
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:chemin*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
