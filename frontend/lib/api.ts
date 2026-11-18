/**
 * Client API minimaliste vers le backend FastAPI.
 *
 * Par défaut, les requêtes partent sur la MÊME origine (/api/...) et Next.js les
 * proxifie vers le backend (voir `rewrites` dans next.config.mjs). Cela évite
 * tout problème de CORS ou de port côté navigateur.
 *
 * En production, on peut définir NEXT_PUBLIC_API_URL pour appeler le backend
 * directement (ex. https://mon-service.onrender.com).
 */

const RAW_API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://foot-predict-api-8hzu.onrender.com";
export const API_BASE = RAW_API_BASE.replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE}${path}`;
  let networkError: unknown = null;

  // Jusqu'à 3 tentatives pour absorber un redémarrage du backend (quelques
  // centaines de millisecondes d'indisponibilité suffisent à faire échouer fetch).
  for (let attempt = 0; attempt < 3; attempt += 1) {
    let response: Response;
    try {
      response = await fetch(url, {
        cache: "no-store",
        signal,
        headers: { Accept: "application/json" },
      });
    } catch (error) {
      if ((error as Error)?.name === "AbortError") throw error;
      networkError = error;
      if (signal?.aborted) throw error;
      await new Promise((resolve) => setTimeout(resolve, 600 * (attempt + 1)));
      continue;
    }

    if (!response.ok) {
      let detail = `Erreur ${response.status}`;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* réponse non JSON : on garde le message générique */
      }
      throw new ApiError(detail, response.status);
    }

    return (await response.json()) as T;
  }

  throw new ApiError(
    `Impossible de joindre l'API (${API_BASE || "même origine (proxy /api)"}). ` +
      `Vérifiez que le backend est démarré (double-clic sur start_backend.bat), ` +
      `puis cliquez sur « Réessayer ». ` +
      `Détail : ${(networkError as Error)?.message ?? "réseau indisponible"}`,
    0,
  );
}
