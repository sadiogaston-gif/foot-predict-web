import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Backend ciblé par le proxy /api (côté serveur Next.js).
// Modifiable via la variable d'environnement API_PROXY_TARGET.
const BACKEND_URL = (process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8011").replace(/\/+$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Le client interroge l'API sur sa propre origine (/api/...). Next.js proxifie
  // ces requêtes vers le backend FastAPI : aucun problème de CORS ni de port.
  // En production, on peut soit définir NEXT_PUBLIC_API_URL (appel direct vers
  // Render), soit définir API_PROXY_TARGET pour conserver le proxy.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
  // Fichier de configuration Next.js situé dans frontend/ : on précise le root
  // de l'espace de travail pour éviter la détection ambiguë (pnpm-lock.json + package-lock.json).
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
