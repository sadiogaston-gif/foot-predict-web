"use client";

import React from "react";

import { leagueByCode } from "@/lib/leagues";

interface Props {
  code: string;
  size?: number;
  className?: string;
}

function hueFromCode(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 360;
  }
  return hash;
}

/**
 * Mapping des codes Football-Data vers les noms sur Wikimedia Commons.
 */
const wikimediaNames: Record<string, string> = {
  "B1": "Jupiler Pro League",
  "E0": "Premier League",
  "E1": "Championship",
  "F1": "Ligue 1",
  "F2": "Ligue 2",
  "D1": "Bundesliga",
  "D2": "2. Bundesliga",
  "I1": "Serie A",
  "I2": "Serie B",
  "SP1": "La Liga",
  "SP2": "Segunda División",
  "P1": "Primeira Liga",
  "P2": "Liga Portugal 2",
  "N1": "Eredivisie",
};

/**
 * Essaie de récupérer l'emblème Wikimedia pour un championnat.
 * Retourne l'URL directe ou null si non trouvé.
 */
async function fetchWikimediaEmblem(leagueCode: string): Promise<string | null> {
  const leagueName = wikimediaNames[leagueCode];
  if (!leagueName) return null;

  const searchTerm = `${leagueName} logo`;
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

    const first = results[0];
    const title = first.title || "";

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
  const hue = hueFromCode(code);

  // État : l'image officielle a-t-elle échoué ? (initialement false)
  const [showFallback, setShowFallback] = React.useState(false);

  // tentative Wikimedia en arrière-plan (ne modifie pas l'affichage immédiatement)
  React.useEffect(() => {
    if (code === "B1" || !league?.logo) {
      fetchWikimediaEmblem(code).then((url) => {
        // Si Wikimedia a trouvé un emblème, on peut le signaler mais on garde
        // l'affichage actuel pour éviter les re-renders problématiques.
        // L'URL pourrait être stockée en localStorage mais pour l'instant
        // on se contente du badge de couleur.
      });
    }
  }, [code]);

  // Si l'image officielle a planté (onError), on bascule sur le fallback
  const handleImageError = () => {
    setShowFallback(true);
  };

  // Si showFallback est true, on affiche le badge de couleur
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
          background: `hsl(${hue} 40% 26%)`,
          color: `hsl(${hue} 75% 82%)`,
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
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={league.logo}
          alt=""
          loading="lazy"
          className={`shrink-0 object-contain ${className}`}
          style={{ width: size, height: size }}
          onError={handleImageError}
        />
      ) : null}

      {/* Badge de couleur en dessous ou à la place */}
      {showFallback ? (
        <span
          aria-hidden
          title={league?.name ?? code}
          className={`flex shrink-0 items-center justify-center rounded-[4px] border border-white/10 font-mono font-semibold ${className}`}
          style={{
            width: size,
            height: size,
            fontSize: Math.max(7, Math.round(size * 0.42)),
            background: `hsl(${hue} 40% 26%)`,
            color: `hsl(${hue} 75% 82%)`,
          }}
        >
          {code}
        </span>
      ) : null}
    </div>
  );
}