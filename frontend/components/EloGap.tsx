"use client";

interface Props {
  home: number;
  away: number;
  homeTeam: string;
  awayTeam: string;
  compact?: boolean;
}

/**
 * Écart Elo entre deux équipes, avec lecture rapide du favori.
 * L'avantage du terrain est déjà inclus dans le Elo renvoyé par le moteur.
 */
export default function EloGap({ home, away, homeTeam, awayTeam }: Props) {
  const delta = home - away;
  const absDelta = Math.abs(delta);
  const leader = delta > 0 ? homeTeam : awayTeam;
  const strong = absDelta >= 100;
  const even = absDelta < 20;

  const color = even
    ? "border-ink-600 text-slate-400"
    : delta > 0
      ? "border-accent/40 bg-accent/10 text-accent"
      : "border-info/40 bg-info/10 text-info";

  // Largeur de la barre de dominance : 0..200+ Elo -> 0..100 %
  const fillPct = Math.min(100, (absDelta / 200) * 100);

  return (
    <div className="flex w-full flex-col items-center gap-1.5 text-center">
      <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-slate-600">
        Écart Elo
      </span>
      <span className={`tnum rounded-md border px-2.5 py-1 font-mono text-[13px] font-semibold ${color}`}>
        {delta > 0 ? "+" : ""}{delta.toFixed(0)}
      </span>
      <span className={`text-[10px] ${even ? "text-slate-600" : "text-slate-400"}`}>
        {even
          ? "Équipes équilibrées"
          : `${strong ? "Net avantage " : "Avantage "}${leader}`}
      </span>
      <div className="mt-0.5 h-1 w-full max-w-[120px] overflow-hidden rounded-full bg-ink-700">
        <div
          className={`h-full rounded-full ${delta > 0 ? "bg-accent" : "bg-info"}`}
          style={{ width: `${fillPct}%`, marginLeft: delta > 0 ? 0 : "auto" }}
        />
      </div>
      <span className="text-[9px] text-slate-600">avantage terrain inclus</span>
    </div>
  );
}