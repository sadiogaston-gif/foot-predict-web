import type { MatchDetail, TeamFormContext } from "@/lib/types";

interface Trend {
  label: string;
  count: number;
  total: number;
  tone: "good" | "neutral" | "bad";
}

function trendLabel(count: number, total: number): string {
  return `${count}/${total}`;
}

/** Construit les tendances « x/y sur les N derniers » façon ValueStats. */
function buildTrends(form: TeamFormContext | undefined): Trend[] {
  if (!form) return [];
  const total = form.overall?.played ?? form.matches?.length ?? 0;
  if (!total) return [];

  const trends: Trend[] = [
    {
      label: "+2.5 buts",
      count: form.over_2_5_count ?? 0,
      total,
      tone: (form.over_2_5_rate ?? 0) >= 50 ? "good" : "neutral",
    },
    {
      label: "BTTS (2 équipes marquent)",
      count: form.btts_count ?? 0,
      total,
      tone: (form.btts_rate ?? 0) >= 50 ? "good" : "neutral",
    },
    {
      label: "Clean sheet",
      count: form.clean_sheets ?? 0,
      total,
      tone: "good",
    },
    {
      label: "N'a pas marqué",
      count: form.failed_to_score ?? 0,
      total,
      tone: "bad",
    },
  ];
  return trends;
}

function TeamTrends({
  team,
  form,
  side,
}: {
  team: string;
  form: TeamFormContext | undefined;
  side: "home" | "away";
}) {
  const trends = buildTrends(form);
  const streak = form?.streak;
  const streakText =
    streak?.type && streak.length > 0
      ? `${streak.length} victoires consécutives`
      : streak?.type === "D" && streak.length > 0
        ? `${streak.length} nuls consécutifs`
        : streak?.type === "L" && streak.length > 0
          ? `${streak.length} défaites consécutives`
          : null;

  if (trends.length === 0) {
    return (
      <div className="rounded-lg border border-ink-700/60 bg-ink-900/40 p-4">
        <p className="text-[13px] font-semibold text-fg">{team}</p>
        <p className="mt-2 text-[11px] text-slate-500">Tendances indisponibles.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-900/40 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-[13px] font-semibold text-fg">{team}</p>
        <span className="chip border-ink-600 text-[9px] uppercase tracking-wider text-slate-500">
          {side === "home" ? "🏠 Domicile" : "✈️ Extérieur"}
        </span>
      </div>

      {streakText ? (
        <p className="mb-3 rounded-md border border-accent/20 bg-accent/5 px-2.5 py-1.5 text-[11px] text-accent">
          Série en cours : {streakText}
        </p>
      ) : null}

      <ul className="space-y-1.5">
        {trends.map((trend) => (
          <li key={trend.label} className="flex items-center justify-between gap-3 text-[11px]">
            <span className="text-slate-400">{trend.label}</span>
            <span
              className={`tnum font-mono font-medium ${
                trend.tone === "good"
                  ? "text-accent"
                  : trend.tone === "bad"
                    ? "text-danger"
                    : "text-slate-300"
              }`}
              title={`${trend.count} occurrence(s) sur les ${trend.total} derniers matchs`}
            >
              {trendLabel(trend.count, trend.total)}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 border-t border-ink-700/50 pt-2 text-[9px] text-slate-600">
        Sur les {trends[0].total} derniers matchs · toutes compétitions
      </p>
    </div>
  );
}

/**
 * Tendances et séries des deux équipes, présentées comme sur ValueStats :
 * « x/y sur les N derniers » pour les buts, BTTS, clean sheets et séries.
 */
export default function TrendsPanel({ match }: { match: MatchDetail }) {
  return (
    <div className="card p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-fg">Tendances &amp; Séries</h2>
        <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
          x/y · L{match.form?.home?.overall?.played ?? "?"}
        </span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <TeamTrends team={match.home_team} form={match.form?.home} side="home" />
        <TeamTrends team={match.away_team} form={match.form?.away} side="away" />
      </div>
    </div>
  );
}