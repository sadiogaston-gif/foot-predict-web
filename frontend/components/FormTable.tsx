import { formatDate } from "@/lib/format";
import type { FormSummary, RecentMatch } from "@/lib/types";

const RESULT_STYLES: Record<RecentMatch["result"], string> = {
  W: "border-accent/40 bg-accent/10 text-accent",
  D: "border-ink-500 bg-ink-700/70 text-slate-300",
  L: "border-danger/40 bg-danger/10 text-danger",
};

const RESULT_LABELS: Record<RecentMatch["result"], string> = {
  W: "V",
  D: "N",
  L: "D",
};

interface FormTableProps {
  team: string;
  matches: RecentMatch[];
  summary: FormSummary;
  accent: "home" | "away";
}

export default function FormTable({ team, matches, summary, accent }: FormTableProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p
          className={`text-sm font-semibold ${
            accent === "home" ? "text-accent" : "text-info"
          }`}
        >
          {team}
        </p>
        <p className="tnum font-mono text-[11px] text-slate-500">
          {summary.points} pts · {summary.wins}V {summary.draws}N {summary.losses}D
        </p>
      </div>

      <table className="table-base">
        <thead>
          <tr>
            <th className="w-[72px] whitespace-nowrap">Date</th>
            <th className="w-8">Lieu</th>
            <th>Adversaire</th>
            <th className="w-14 text-right">Score</th>
            <th className="w-10 text-right">Rés.</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((match, index) => (
            <tr key={`${match.date}-${match.opponent}-${index}`}>
              <td className="tnum whitespace-nowrap font-mono text-[11px] text-slate-500">
                {formatDate(match.date)}
              </td>
              <td className="font-mono text-[11px] text-slate-500">{match.venue}</td>
              <td className="max-w-[140px] truncate text-[13px]">{match.opponent}</td>
              <td className="tnum text-right font-mono text-[12px] text-slate-200">
                {match.goals_for}–{match.goals_against}
              </td>
              <td className="text-right">
                <span
                  className={`inline-flex h-5 w-5 items-center justify-center rounded border font-mono text-[10px] font-semibold ${RESULT_STYLES[match.result]}`}
                >
                  {RESULT_LABELS[match.result]}
                </span>
              </td>
            </tr>
          ))}
          {matches.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-4 text-center text-[12px] text-slate-500">
                Aucun match récent disponible.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>

      <p className="tnum font-mono text-[11px] text-slate-500">
        Moy. buts marqués {summary.avg_goals_for.toFixed(2)} · encaissés{" "}
        {summary.avg_goals_against.toFixed(2)}
      </p>
    </div>
  );
}
