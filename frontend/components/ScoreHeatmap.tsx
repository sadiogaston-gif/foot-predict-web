import type { ScoreMatrix } from "@/lib/types";

/**
 * Heatmap des probabilités de scores exacts (0-0 à 5-5).
 * Intensité de la couleur proportionnelle à la probabilité du score.
 */
export default function ScoreHeatmap({ matrix }: { matrix: ScoreMatrix }) {
  const flat = matrix.rows.flatMap((row) => row.probabilities);
  const max = Math.max(...flat, 0.0001);
  const topScore = flat.indexOf(max);
  const topRow = Math.floor(topScore / matrix.goals.length);
  const topCol = topScore % matrix.goals.length;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[420px]">
        <div
          className="grid items-center gap-1"
          style={{ gridTemplateColumns: `44px repeat(${matrix.goals.length}, minmax(0, 1fr))` }}
        >
          <div className="text-center font-mono text-[10px] uppercase tracking-wider text-slate-600">
            H\A
          </div>
          {matrix.goals.map((goal) => (
            <div
              key={`head-${goal}`}
              className="text-center font-mono text-[11px] text-slate-500"
            >
              {goal}
            </div>
          ))}

          {matrix.rows.map((row, rowIndex) => (
            <div key={`row-${row.goals_home}`} className="contents">
              <div className="pr-2 text-right font-mono text-[11px] text-slate-500">
                {row.goals_home}
              </div>
              {row.probabilities.map((probability, colIndex) => {
                const intensity = probability / max;
                const isTop = rowIndex === topRow && colIndex === topCol;
                return (
                  <div
                    key={`cell-${row.goals_home}-${colIndex}`}
                    className={`tnum flex aspect-square items-center justify-center rounded-md border font-mono text-[10px] transition sm:text-[11px] ${
                      isTop
                        ? "border-accent/70 text-accent ring-1 ring-accent/40"
                        : "border-ink-700/40 text-slate-400"
                    }`}
                    style={{
                      backgroundColor: `rgba(0, 224, 138, ${0.04 + intensity * 0.55})`,
                    }}
                    title={`Score ${row.goals_home}-${colIndex} : ${probability.toFixed(2)}%`}
                  >
                    {probability >= 0.1 ? probability.toFixed(1) : "·"}
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between text-[11px] text-slate-500">
          <span>
            Score le plus probable :{" "}
            <span className="font-mono text-accent">
              {topRow}-{topCol}
            </span>{" "}
            ({max.toFixed(1)} %)
          </span>
          <span className="flex items-center gap-2">
            <span className="h-2 w-16 rounded-full bg-gradient-to-r from-ink-800 to-accent/70" />
            <span>probabilité</span>
          </span>
        </div>
      </div>
    </div>
  );
}
