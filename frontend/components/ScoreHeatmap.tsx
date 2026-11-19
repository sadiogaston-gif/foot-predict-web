import type { ScoreMatrix } from "@/lib/types";

/**
 * Heatmap des probabilités de scores exacts (matrice domicile / extérieur).
 * Intensité de la couleur proportionnelle à la probabilité du score.
 * Reprend le design de l'ancien site : dégradé vert, score le plus probable
 * entouré, légende et rappel du score favori.
 */
export default function ScoreHeatmap({ matrix }: { matrix: ScoreMatrix }) {
  const flat = matrix.rows.flatMap((row) => row.probabilities);
  const max = Math.max(...flat, 0.0001);
  const topScore = flat.indexOf(max);
  const topRow = Math.floor(topScore / matrix.goals.length);
  const topCol = topScore % matrix.goals.length;

  const goals = matrix.goals;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[420px]">
        <div
          className="grid items-center gap-1"
          style={{ gridTemplateColumns: `46px repeat(${goals.length}, minmax(0, 1fr))` }}
        >
          {/* Coin : en-têtes domicile \ extérieur */}
          <div className="flex flex-col items-center justify-center text-center font-mono text-[9px] leading-tight uppercase tracking-wider text-slate-600">
            <span>Dom</span>
            <span className="text-slate-700">╲ Ext</span>
          </div>
          {goals.map((goal) => (
            <div
              key={`head-${goal}`}
              className="text-center font-mono text-[11px] font-medium text-slate-400"
            >
              {goal}
            </div>
          ))}

          {matrix.rows.map((row, rowIndex) => (
            <div key={`row-${row.goals_home}`} className="contents">
              <div className="pr-2 text-right font-mono text-[11px] font-medium text-slate-400">
                {row.goals_home}
              </div>
              {row.probabilities.map((probability, colIndex) => {
                const intensity = probability / max;
                const isTop = rowIndex === topRow && colIndex === topCol;
                // Dégradé vert : du très translucide au vert accent saturé.
                const alpha = 0.05 + Math.pow(intensity, 0.7) * 0.65;
                return (
                  <div
                    key={`cell-${row.goals_home}-${colIndex}`}
                    className={`tnum flex aspect-square items-center justify-center rounded-md border font-mono text-[10px] transition sm:text-[11px] ${
                      isTop
                        ? "border-accent text-accent ring-2 ring-accent/50"
                        : "border-ink-700/40 text-slate-300 hover:border-ink-600"
                    }`}
                    style={{ backgroundColor: `rgba(0, 224, 138, ${alpha})` }}
                    title={`Score ${row.goals_home}-${goals[colIndex]} : ${probability.toFixed(2)} %`}
                  >
                    {probability >= 0.1 ? probability.toFixed(1) : "·"}
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Légende + score le plus probable */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-[11px] text-slate-500">
          <span>
            Score le plus probable :{" "}
            <span className="font-mono font-semibold text-accent">
              {topRow}-{topCol}
            </span>{" "}
            <span className="font-mono text-slate-400">({max.toFixed(1)} %)</span>
          </span>
          <span className="flex items-center gap-2">
            <span>Faible</span>
            <span className="h-2 w-20 rounded-full bg-gradient-to-r from-ink-800 via-accent/40 to-accent" />
            <span>Fort</span>
          </span>
        </div>
      </div>
    </div>
  );
}