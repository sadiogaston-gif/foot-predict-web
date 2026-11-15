import { pct } from "@/lib/format";
import type { TeamFormContext } from "@/lib/types";

const RESULT_STYLE: Record<string, string> = {
  W: "bg-accent/85 text-ink-950",
  D: "bg-slate-500/70 text-fg",
  L: "bg-danger/85 text-fg",
};

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-ink-700/70 bg-ink-900/60 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="tnum mt-0.5 font-mono text-[13px] text-slate-100">{value}</p>
      {hint ? <p className="text-[9px] text-slate-600">{hint}</p> : null}
    </div>
  );
}

export default function FormStats({ form }: { form: TeamFormContext }) {
  // `matches` arrive du plus récent au plus ancien : on affiche du plus ancien au plus récent.
  const strip = [...form.matches].reverse();

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1">
        {strip.map((match, index) => (
          <span
            key={`${match.date}-${index}`}
            title={`${match.venue === "H" ? "vs" : "@"} ${match.opponent} : ${match.goals_for}-${match.goals_against}`}
            className={`flex h-5 w-5 items-center justify-center rounded font-mono text-[10px] font-semibold ${RESULT_STYLE[match.result]}`}
          >
            {match.result}
          </span>
        ))}
        <span className="ml-2 text-[10px] text-slate-500">{form.matches.length} matchs</span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat
          label="Bilan"
          value={`${form.overall.wins}V ${form.overall.draws}N ${form.overall.losses}D`}
          hint={`${form.overall.points_per_game} pt/match`}
        />
        <Stat
          label="Buts"
          value={`${form.overall.goals_for} / ${form.overall.goals_against}`}
          hint={`diff ${form.overall.goal_difference > 0 ? "+" : ""}${form.overall.goal_difference}`}
        />
        <Stat
          label="Domicile"
          value={`${form.home.wins}V ${form.home.draws}N ${form.home.losses}D`}
          hint={`${form.home.points_per_game} pt/match`}
        />
        <Stat
          label="Extérieur"
          value={`${form.away.wins}V ${form.away.draws}N ${form.away.losses}D`}
          hint={`${form.away.points_per_game} pt/match`}
        />
        <Stat
          label="Clean sheets"
          value={`${form.clean_sheets}`}
          hint={`${pct(form.clean_sheet_rate, 0)} des matchs`}
        />
        <Stat
          label="BTTS"
          value={pct(form.btts_rate, 0)}
          hint={`${form.btts_count} matchs`}
        />
        <Stat
          label="Over 2.5"
          value={pct(form.over_2_5_rate, 0)}
          hint={`${form.over_2_5_count} matchs`}
        />
        <Stat label="Série" value={form.streak.label} />
        <Stat
          label="Repos"
          value={form.rest_days === null ? "—" : `${form.rest_days} j`}
          hint={`${form.matches_last_14_days} match(s) en 14 j`}
        />
        <Stat
          label="Tendance Elo"
          value={
            form.elo_trend
              ? `${form.elo_trend.delta_5 > 0 ? "+" : ""}${form.elo_trend.delta_5}`
              : "—"
          }
          hint={form.elo_trend ? `Elo ${form.elo_trend.current}` : "5 derniers matchs"}
        />
      </div>
    </div>
  );
}
