"use client";

import React from "react";

import { leagueByCode } from "@/lib/leagues";

interface Props {
  code: string;
  size?: number;
  className?: string;
}

/**
 * Essaie de récupérer l'emblème Wikimedia pour un championnat.
 * Retourne l'URL directe ou null si non trouvé.
 */
async function fetchWikimediaEmblem(leagueCode: string): Promise<string | null> {
  const league = leagueByCode(leagueCode);
  if (!league) return null;

  const searchTerm = `${league.name} logo`;
  try {
    const response = await fetch(
      `https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(searchTerm)}&format=json&srlimit=1`,
      {
        headers: {
          "User-Agent": "FootPredict/1.0 (football prediction platform)",
        },
        cache: "force-cache",
        next: { revalidate: 86400 },
      }
    );

    if (!response.ok) return null;
    const data = await response.json();
    const results = (data.query || {}).search || [];
    if (!results.length) return null;

    const title = results[0].title || "";

    const imgResponse = await fetch(
      `https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url&iiurlwidth=200&titles=${encodeURIComponent(title)}&format=json`,
      {
        headers: {
          "User-Agent": "FootPredict/1.0 (football prediction platform)",
        },
        cache: "force-cache",
        next: { revalidate: 86400 },
      }
    );

    if (!imgResponse.ok) return null;
    const imgData = await imgResponse.json();
    const pages = imgData.query?.pages || {};
    const pageId = Object.keys(pages)[0] || "";
    const page = pages[pageId] || {};

    return page.imageinfo?.[0]?.url || null;
  } catch {
    return null;
  }
}

export default function LeagueBadge({ code, size = 16, className = "" }: Props) {
  const league = leagueByCode(code);
  const [showFallback, setShowFallback] = React.useState(false);

  // tentative Wikimedia en arrière-plan (ne modifie pas l'affichage immédiatement)
  React.useEffect(() => {
    fetchWikimediaEmblem(code).then(() => {
      // Si Wikimedia a trouvé un emblème, on garde l'affichage actuel
      // pour éviter les re-renders problématiques. L'URL pourrait être
      // stockée en localStorage mais pour l'instant on se contente du badge.
    });
  }, [code]);

  const handleImageError = () => setShowFallback(true);

  // Si l'image officielle a planté, on bascule sur le badge de couleur
  if (showFallback) {
    return (
      <span
        aria-hidden
        title={league?.name ?? code}
        className={`flex shrink-0 items-center justify-center rounded-[4px] border border-white/10 font-mono font-semibold ${className}`}
        style={{
          width: size,
          height: size,
          fontSize: Math.max(7, Math.round(size * 0.42)),
          background: "hsl(190 60% 20%)",
          color: "hsl(190 70% 80%)",
        }}
      >
        {code}
      </span>
    );
  }

  // Affichage normal : emblème officiel ou badge de couleur
  return (
    <div className="relative">
      {league?.logo ? (
        <img
          src={league.logo}
          alt=""
          loading="lazy"
          className={`shrink-0 object-contain ${className}`}
          style={{ width: size, height: size }}
          onError={handleImageError}
        />
      ) : null}

      {showFallback ? (
        <span
          aria-hidden
          title={league?.name ?? code}
          className={`flex shrink-0 items-center justify-center rounded-[4px] border border-white/10 font-mono font-semibold ${className}`}
          style={{
            width: size,
            height: size,
            fontSize: Math.max(7, Math.round(size * 0.42)),
            background: "hsl(190 20% 15%)",
            color: "hsl(190 70% 80%)",
          }}
        >
          {code}
        </span>
      ) : null}
    </div>
  );
}
