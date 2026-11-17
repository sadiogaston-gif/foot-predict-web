"use client";

import React from "react";

/**
 * Logo d'une équipe, ou badge généré si aucun logo officiel n'est disponible.
 *
 * Le badge utilise les initiales du club et une teinte déterministe (même club
 * = même couleur), ce qui garantit une identité visuelle pour tous les clubs.
 */

interface Props {
  name: string;
  logo?: string | null;
  size?: number;
  className?: string;
}

function hueFromName(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 360;
  }
  return hash;
}

function initials(name: string): string {
  const words = name
    .replace(/[^A-Za-zÀ-ÖØ-öø-ÿ0-9 ]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

export default function TeamBadge({ name, logo, size = 20, className = "" }: Props) {
  const [showFallback, setShowFallback] = React.useState(false);
  const hue = hueFromName(name);

  const handleImageError = () => setShowFallback(true);

  if (logo && !showFallback) {
    return (
      <img
        src={logo}
        alt=""
        loading="lazy"
        onError={handleImageError}
        className={`shrink-0 object-contain ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <span
      aria-hidden
      title={name}
      className={`flex shrink-0 items-center justify-center rounded-full border border-white/10 font-mono font-semibold ${className}`}
      style={{
        width: size,
        height: size,
        fontSize: Math.max(8, Math.round(size * 0.34)),
        background: `hsl(${hue} 35% 18%)`,
        color: `hsl(${hue} 80% 80%)`,
      }}
    >
      {initials(name)}
    </span>
  );
}
