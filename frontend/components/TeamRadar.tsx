import type { MatchDetail } from "@/lib/types";

type Side = "home" | "away";

interface RadarData {
  team: string;
  values: number[]; // 7 valeurs normalisées 0..100
}

const AXES = [
  "Attaque",
  "Création",
  "Défense",
  "Bloc",
  "Forme",
  "Clean sheets",
  "Elo",
];

const clamp = (v: number, min = 0, max = 100) => Math.max(min, Math.min(max, v));

/** Construit les 7 axes à partir des données réelles du match. */
function buildRadar(match: MatchDetail, side: Side): RadarData {
  const form = match.form?.[side]?.overall;
  const forces = match.forces?.[side];
  const elo = match.elo?.[side] ?? 1500;
  const lambda = match.lambdas?.[side] ?? 1.2;
  const cleanSheetRate = match.form?.[side]?.clean_sheet_rate ?? 0;

  return {
    team: side === "home" ? match.home_team : match.away_team,
    values: [
      // Attaque : index de force (typique 0.5–1.6)
      clamp(((forces?.attack ?? 1) - 0.5) / 1.1 * 100),
      // Création : buts attendus / lambda (typique 0.3–3.2)
      clamp((lambda / 3.2) * 100),
      // Défense : index inversé (bas = meilleur)
      clamp(((1.6 - (forces?.defense ?? 1)) / 1.1) * 100),
      // Bloc : buts concédés par match inversés (0.4–2.6)
      clamp(((2.6 - (form?.goals_against ?? 1.3)) / 2.2) * 100),
      // Forme : points par match (0–3)
      clamp(((form?.points_per_game ?? 1.4) / 3) * 100),
      // Clean sheets : taux 0–1
      clamp(cleanSheetRate * 100),
      // Elo : échelle 1100–2000
      clamp(((elo - 1100) / 900) * 100),
    ],
  };
}

function polarPoint(cx: number, cy: number, radius: number, index: number, total: number) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
}

function polygonPoints(values: number[], cx: number, cy: number, radius: number) {
  return values
    .map((v, i) => {
      const p = polarPoint(cx, cy, (v / 100) * radius, i, values.length);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    })
    .join(" ");
}

/**
 * Radar comparatif domicile / extérieur façon DataMB (7 axes), en SVG pur.
 * Les axes sont normalisés à partir des données réelles du modèle (forces,
 * lambda, Elo, forme, clean sheets) — aucune donnée externe requise.
 */
export default function TeamRadar({ match }: { match: MatchDetail }) {
  const home = buildRadar(match, "home");
  const away = buildRadar(match, "away");

  const size = 300;
  const cx = size / 2;
  const cy = size / 2 + 6;
  const radius = 104;
  const rings = [0.25, 0.5, 0.75, 1];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-center gap-4 text-[11px]">
        <span className="flex items-center gap-1.5 text-slate-300">
          <span className="h-2.5 w-2.5 rounded-sm bg-accent/70 ring-1 ring-accent" />
          {home.team}
        </span>
        <span className="flex items-center gap-1.5 text-slate-300">
          <span className="h-2.5 w-2.5 rounded-sm bg-info/70 ring-1 ring-info" />
          {away.team}
        </span>
      </div>

      <div className="flex justify-center">
        <svg
          viewBox={`0 0 ${size} ${size}`}
          className="h-auto w-full max-w-[320px]"
          role="img"
          aria-label={`Radar comparatif : ${home.team} contre ${away.team}`}
        >
          {/* Grille : cercles concentriques */}
          {rings.map((r) => (
            <polygon
              key={`ring-${r}`}
              points={polygonPoints(AXES.map(() => r * 100), cx, cy, radius)}
              fill="none"
              stroke="currentColor"
              strokeWidth={1}
              className="text-ink-700/60"
            />
          ))}

          {/* Axes + libellés */}
          {AXES.map((label, i) => {
            const outer = polarPoint(cx, cy, radius, i, AXES.length);
            const textPoint = polarPoint(cx, cy, radius + 20, i, AXES.length);
            return (
              <g key={`axis-${label}`}>
                <line
                  x1={cx}
                  y1={cy}
                  x2={outer.x}
                  y2={outer.y}
                  stroke="currentColor"
                  strokeWidth={1}
                  className="text-ink-700/50"
                />
                <text
                  x={textPoint.x}
                  y={textPoint.y}
                  fill="currentColor"
                  className="fill-slate-400 text-[9px]"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {label}
                </text>
              </g>
            );
          })}

          {/* Polygones des équipes */}
          <polygon
            points={polygonPoints(away.values, cx, cy, radius)}
            fill="rgba(56, 189, 248, 0.12)"
            stroke="currentColor"
            strokeWidth={2}
            className="text-info"
          />
          <polygon
            points={polygonPoints(home.values, cx, cy, radius)}
            fill="rgba(0, 224, 138, 0.14)"
            stroke="currentColor"
            strokeWidth={2}
            className="text-accent"
          />

          {/* Points */}
          {home.values.map((v, i) => {
            const p = polarPoint(cx, cy, (v / 100) * radius, i, AXES.length);
            return (
              <circle key={`home-dot-${i}`} cx={p.x} cy={p.y} r={2.5} className="fill-accent" />
            );
          })}
          {away.values.map((v, i) => {
            const p = polarPoint(cx, cy, (v / 100) * radius, i, AXES.length);
            return (
              <circle key={`away-dot-${i}`} cx={p.x} cy={p.y} r={2.5} className="fill-info" />
            );
          })}
        </svg>
      </div>

      <p className="text-center text-[10px] leading-relaxed text-slate-600">
        Axes normalisés (0–100) à partir des données du modèle : forces, buts attendus,
        Elo, forme et clean sheets.
      </p>
    </div>
  );
}