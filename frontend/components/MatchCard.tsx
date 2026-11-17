import Link from "next/link";
import LeagueBadge from "@/components/LeagueBadge";
import ProbabilityBar from "@/components/ProbabilityBar";
import TeamBadge from "@/components/TeamBadge";
import ValueBadge from "@/components/ValueBadge";
import { formatDate, formatTime, odds, pct } from "@/lib/format";
import type { MatchSummary } from "@/lib/types";

function OddsCell({
  book,
  fair,
}: {
  book: number | null | undefined;
  fair: number | null | undefined;
}) {
  const isValue = book != null && fair != null && book > fair * 1.02;
  return (
    <span
      className={`tnum font-mono text-[11px] ${
        isValue ? "font-semibold text-accent" : "text-slate-300"
      }`}
      title={fair != null ? `Cote juste du modèle : ${odds(fair)}` : undefined}
    >
      {odds(book)}
    </span>
  );
}

export default function MatchCard({ match }: { match: MatchSummary }) {
  const homeFavorite = match.probabilities.home >= match.probabilities.away;
  const best = match.best_value;
  const hasMarketOdds =
    match.odds.home != null || match.odds.draw != null || match.odds.away != null;

  return (
    <Link
      href={`/match/${match.id}`}
      className="card group relative flex flex-col gap-4 p-4 transition duration-200 hover:-translate-y-1 hover:border-accent/50 hover:bg-ink-800 link-focus"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="chip border-ink-600 bg-ink-800 text-[10px] text-slate-300">
          <LeagueBadge code={match.league_code} size={14} />
          {match.league}
        </span>
        <span className="tnum font-mono text-[11px] uppercase tracking-wide text-slate-500">
          {formatDate(match.date)} · {formatTime(match.time)}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2">
            <TeamBadge name={match.home_team} logo={match.home_logo} size={20} />
            <span
              className={`truncate text-[15px] ${
                homeFavorite ? "font-semibold text-fg" : "font-medium text-slate-300"
              }`}
            >
              {match.home_team}
            </span>
          </span>
          <span className="tnum shrink-0 font-mono text-[11px] text-slate-500">
            {match.elo.home.toFixed(0)}
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2">
            <TeamBadge name={match.away_team} logo={match.away_logo} size={20} />
            <span
              className={`truncate text-[15px] ${
                !homeFavorite ? "font-semibold text-fg" : "font-medium text-slate-300"
              }`}
            >
              {match.away_team}
            </span>
          </span>
          <span className="tnum shrink-0 font-mono text-[11px] text-slate-500">
            {match.elo.away.toFixed(0)}
          </span>
        </div>
      </div>

      <ProbabilityBar
        home={match.probabilities.home}
        draw={match.probabilities.draw}
        away={match.probabilities.away}
      />

      <div className="grid grid-cols-[auto_1fr_1fr_1fr] items-center gap-x-1 gap-y-1 rounded-lg border border-ink-700/70 bg-ink-900/60 px-2 py-2 sm:grid-cols-[auto_1fr_1fr_1fr] sm:gap-x-2 sm:px-3 sm:py-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Cotes
        </span>
        <span className="text-center font-mono text-[10px] text-slate-500">1</span>
        <span className="text-center font-mono text-[10px] text-slate-500">X</span>
        <span className="text-center font-mono text-[10px] text-slate-500">2</span>

        <span className="text-[10px] uppercase tracking-wide text-slate-500">Marché</span>
        <span className="text-center">
          <OddsCell book={match.odds.home} fair={match.fair_odds.home} />
        </span>
        <span className="text-center">
          <OddsCell book={match.odds.draw} fair={match.fair_odds.draw} />
        </span>
        <span className="text-center">
          <OddsCell book={match.odds.away} fair={match.fair_odds.away} />
        </span>

        <span className="text-[10px] uppercase tracking-wide text-slate-500">Juste</span>
        <span className="tnum text-center font-mono text-[12px] text-slate-500">
          {odds(match.fair_odds.home)}
        </span>
        <span className="tnum text-center font-mono text-[12px] text-slate-500">
          {odds(match.fair_odds.draw)}
        </span>
        <span className="tnum text-center font-mono text-[12px] text-slate-500">
          {odds(match.fair_odds.away)}
        </span>
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-ink-700/60 pt-3">
        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="text-slate-500">O2.5</span>
            <span className="tnum font-mono text-slate-300">{pct(match.over_2_5, 0)}</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="text-slate-500">BTTS</span>
            <span className="tnum font-mono text-slate-300">{pct(match.btts_yes, 0)}</span>
          </div>
          {match.top_scores[0] ? (
            <span className="sm:hidden flex items-center gap-2 text-[11px] text-slate-400">
              <span className="text-slate-500">Score</span>
              <span className="tnum font-mono text-slate-300">{match.top_scores[0].score}</span>
            </span>
          ) : null}
        </div>

        {best ? (
          <ValueBadge ev={best.ev_percent} label={best.label} size="sm" />
        ) : hasMarketOdds ? (
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-600">
            Pas de value
          </span>
        ) : (
          <span
            className="font-mono text-[10px] uppercase tracking-wider text-slate-600"
            title="Aucune cote bookmaker disponible pour cette affiche : impossible de calculer la value."
          >
            Cotes indisponibles
          </span>
        )}
      </div>
    </Link>
  );
}
