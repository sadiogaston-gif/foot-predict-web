"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import TeamBadge from "@/components/TeamBadge";
import LeagueBadge from "@/components/LeagueBadge";
import CountryFlag from "@/components/CountryFlag";
import ValueBadge from "@/components/ValueBadge";
import ProbabilityBar from "@/components/ProbabilityBar";
import ScoreHeatmap from "@/components/ScoreHeatmap";
import { apiGet } from "@/lib/api";
import { formatDate, formatKickoffTime, odds, pct, signedPct } from "@/lib/format";
import type { MatchDetail } from "@/lib/types";

export default function MatchDetailPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!matchId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiGet<MatchDetail>(`/api/matches/${matchId}`);
      setMatch(response);
    } catch (err: any) {
      setError(err?.message ?? "Match introuvable");
    } finally {
      setLoading(false);
    }
  }, [matchId]);

  useEffect(() => {
    load();
  }, [load, matchId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-8 w-8 rounded-full border-4 border-ink-700 border-t-accent animate-spin" />
          <p className="text-sm text-slate-400">Chargement du match...</p>
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center px-4 sm:px-10">
        <p className="text-danger text-sm font-semibold">{error || "Match introuvable"}</p>
        <Link
          href="/"
          className="mt-4 btn-ghost link-focus text-[12px]"
        >
          Retour à l'accueil
        </Link>
      </div>
    );
  }

  const best = match.best_value;

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row items-start justify-between gap-4">
        <div className="flex-1">
          <Link href="/" className="link-focus text-[11px] font-medium text-accent/80 hover:text-accent">
            ← Retour aux matchs
          </Link>
          <h1 className="text-[24px] font-semibold tracking-tight text-fg sm:text-3xl mt-2">
            {match.home_team} vs {match.away_team}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <CountryFlag country={match.country} size={16} />
            <LeagueBadge code={match.league_code} size={16} />
            <span className="text-[12px] font-medium text-slate-500">{match.league}</span>
            <span className="text-[11px] px-2 py-0.5 rounded-md border border-ink-600 bg-ink-800 text-slate-500">
              {match.country}
            </span>
          </div>
        </div>
        <div className="tnum text-right font-mono text-[11px] leading-relaxed text-slate-500 sm:text-left">
          <p>{formatDate(match.date)}</p>
          <p title="Coup d'envoi à l'heure locale de votre appareil">
            {formatKickoffTime(match.date, match.time)}
          </p>
        </div>
      </div>

      {/* Match header with teams */}
      <div className="card p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 text-right">
            <div className="flex flex-col items-end gap-1">
              <span className="flex items-center gap-2">
                <TeamBadge name={match.home_team} logo={match.home_logo} size={48} />
                <span className="text-[18px] font-bold text-fg">{match.home_team}</span>
              </span>
              <span className="tnum font-mono text-lg font-semibold text-fg">
                {match.elo.home.toFixed(0)}
              </span>
            </div>
          </div>
          <div className="flex flex-col items-center gap-2">
            <ProbabilityBar
              home={match.probabilities.home}
              draw={match.probabilities.draw}
              away={match.probabilities.away}
              compact
            />
            <div className="flex gap-2">
              <span className="tnum font-mono text-[11px] text-accent">{match.probabilities.home.toFixed(0)}%</span>
              <span className="tnum font-mono text-[11px] text-slate-400">{match.probabilities.draw.toFixed(0)}%</span>
              <span className="tnum font-mono text-[11px] text-info">{match.probabilities.away.toFixed(0)}%</span>
            </div>
          </div>
          <div className="flex-1 flex flex-col items-start gap-1">
            <span className="flex items-center gap-2">
              <TeamBadge name={match.away_team} logo={match.away_logo} size={48} />
              <span className="text-[18px] font-bold text-fg">{match.away_team}</span>
            </span>
            <span className="tnum font-mono text-lg font-semibold text-fg">
              {match.elo.away.toFixed(0)}
            </span>
          </div>
        </div>
      </div>

      {/* Probabilities */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Probabilités du modèle
          </span>
        </div>
        <ProbabilityBar
          home={match.probabilities.home}
          draw={match.probabilities.draw}
          away={match.probabilities.away}
        />
      </div>

      {/* Odds grid */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Cotes bookmaker vs modèle
          </span>
        </div>
        <div className="grid grid-cols-[auto_1fr_1fr_1fr] items-center gap-x-1 gap-y-1 rounded-lg border border-ink-700/70 bg-ink-900/60 px-2 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Marché</span>
          <span className="text-center font-mono text-[10px] text-slate-500">1</span>
          <span className="text-center font-mono text-[10px] text-slate-500">X</span>
          <span className="text-center font-mono text-[10px] text-slate-500">2</span>

          <span className="text-[10px] uppercase tracking-wide text-slate-500">Cote marché</span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">
              {odds(match.odds.home)}
            </span>
          </span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">
              {odds(match.odds.draw)}
            </span>
          </span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">
              {odds(match.odds.away)}
            </span>
          </span>

          <span className="text-[10px] uppercase tracking-wider text-slate-500">Cote juste</span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">
              {odds(match.fair_odds.home)}
            </span>
          </span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">
              {odds(match.fair_odds.draw)}
            </span>
          </span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">
              {odds(match.fair_odds.away)}
            </span>
          </span>

          <span className="text-[10px] uppercase tracking-wider text-slate-500">Prob. modèle</span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">{pct(match.probabilities.home, 0)}%</span>
          </span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">{pct(match.probabilities.draw, 0)}%</span>
          </span>
          <span className="text-center">
            <span className="tnum font-mono text-[12px] text-slate-300">{pct(match.probabilities.away, 0)}%</span>
          </span>
        </div>
      </div>

      {/* Value bets */}
      {match.is_value_bet && best ? (
        <div className="card border-accent/50 bg-accent/10 p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-accent font-mono font-bold uppercase tracking-wider text-[11px]">
                  Value Bet détecté
                </span>
                <ValueBadge ev={best.ev_percent} label={best.label} size="sm" />
              </div>
              <p className="text-sm text-slate-300">
                Le modèle estime une probabilité de{" "}
                <span className="font-semibold text-fg">{pct(best.model_probability)}%</span>{" "}
                pour ce résultat, contre une cote de marché de{" "}
                <span className="font-semibold text-fg">{odds(best.book_odds)}</span>.
              </p>
            </div>
            <div className="tnum font-mono text-lg font-semibold text-accent">
              EV {signedPct(best.ev_percent)}
            </div>
          </div>
        </div>
      ) : (
        <div className="card p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Value bet
            </span>
            <span className="font-mono text-[11px] text-slate-500">
              Aucune value bet détectée sur ce match
            </span>
          </div>
        </div>
      )}

      {/* Score matrix — heatmap façon ancien design */}
      <div className="card p-5">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-fg">
            Probabilités des scores exacts
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
            Dixon-Coles
          </span>
        </div>
        <div className="mt-4">
          <ScoreHeatmap matrix={match.score_matrix} />
        </div>
      </div>

      {/* Form section */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Forme {match.recent.home.team}
            </span>
          </div>
          <div className="space-y-1">
            {match.recent.home.matches.map((m) => (
              <div key={`${m.date}-${m.opponent}`} className="flex items-center gap-2 text-[11px]">
                <span className="text-[10px] font-mono text-slate-500">{m.date}</span>
                <span className="truncate text-slate-300">{m.opponent}</span>
                <span className={`tnum font-mono text-[10px] ${
                  m.result === "W" ? "text-emerald-400" : m.result === "D" ? "text-amber-400" : "text-danger"
                }`}>
                  {m.result}
                </span>
                <span className="tnum font-mono text-[10px] text-slate-400">
                  {m.goals_for}-{m.goals_against}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Forme {match.recent.away.team}
            </span>
          </div>
          <div className="space-y-1">
            {match.recent.away.matches.map((m) => (
              <div key={`${m.date}-${m.opponent}`} className="flex items-center gap-2 text-[11px]">
                <span className="text-[10px] font-mono text-slate-500">{m.date}</span>
                <span className="truncate text-slate-300">{m.opponent}</span>
                <span className={`tnum font-mono text-[10px] ${
                  m.result === "W" ? "text-emerald-400" : m.result === "D" ? "text-amber-400" : "text-danger"
                }`}>
                  {m.result}
                </span>
                <span className="tnum font-mono text-[10px] text-slate-400">
                  {m.goals_for}-{m.goals_against}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* External context */}
      {match.external.available && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Contexte externe
            </span>
          </div>
          {match.external.injuries && match.external.injuries.home && match.external.injuries.home.length > 0 ? (
            <div className="mb-3">
              <span className="text-[11px] font-semibold text-slate-500">Blessures domicile</span>
              <ul className="mt-1 space-y-1 text-[11px] text-slate-300">
                {match.external.injuries.home.map((inj) => (
                  <li key={inj.player} className="flex items-center gap-2">
                    <span className="text-slate-500">{inj.player}</span>
                    <span className="text-[10px] text-danger">{inj.type}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
