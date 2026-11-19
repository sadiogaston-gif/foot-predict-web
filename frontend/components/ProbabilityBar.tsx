import { pct } from "@/lib/format";

interface ProbabilityBarProps {
  home: number;
  draw: number;
  away: number;
  compact?: boolean;
}

/**
 * Barre tricolore 1 / X / 2.
 * Les largeurs sont proportionnelles aux probabilités du modèle.
 * Les pourcentages sont alignés sur une grille 3 colonnes : le « 1 » à gauche,
 * le « X » au centre et le « 2 » à droite, comme les segments de la barre.
 */
export default function ProbabilityBar({ home, draw, away, compact = false }: ProbabilityBarProps) {
  const total = Math.max(home + draw + away, 0.0001);
  const homeWidth = (home / total) * 100;
  const drawWidth = (draw / total) * 100;

  return (
    <div className="space-y-2">
      <div
        className={`flex w-full overflow-hidden rounded-full bg-ink-700 ${
          compact ? "h-1.5" : "h-2.5"
        }`}
        role="img"
        aria-label={`Domicile ${pct(home)}, Nul ${pct(draw)}, Extérieur ${pct(away)}`}
      >
        <div style={{ width: `${homeWidth}%` }} className="bg-accent transition-[width] duration-500" />
        <div style={{ width: `${drawWidth}%` }} className="bg-slate-500" />
        <div style={{ width: `${100 - homeWidth - drawWidth}%` }} className="bg-info" />
      </div>

      <div className={`grid grid-cols-3 gap-1 ${compact ? "text-[10px]" : "text-[11px]"}`}>
        <span className="flex items-baseline justify-start gap-1.5">
          <span className="font-mono text-[10px] font-semibold text-accent">1</span>
          <span className="tnum text-slate-200">{pct(home, 0)}</span>
        </span>
        <span className="flex items-baseline justify-center gap-1.5">
          <span className="font-mono text-[10px] font-semibold text-slate-400">X</span>
          <span className="tnum text-slate-200">{pct(draw, 0)}</span>
        </span>
        <span className="flex items-baseline justify-end gap-1.5">
          <span className="font-mono text-[10px] font-semibold text-info">2</span>
          <span className="tnum text-slate-200">{pct(away, 0)}</span>
        </span>
      </div>
    </div>
  );
}