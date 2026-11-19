"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import EloChart from "@/components/EloChart";
import ExternalContextSection from "@/components/ExternalContext";
import FormStats from "@/components/FormStats";
import FormTable from "@/components/FormTable";
import KellySimulator from "@/components/KellySimulator";
import LeagueBadge from "@/components/LeagueBadge";
import CountryFlag from "@/components/CountryFlag";
import ScoreHeatmap from "@/components/ScoreHeatmap";
import TeamBadge from "@/components/TeamBadge";
import ValueBadge from "@/components/ValueBadge";
import { apiGet } from "@/lib/api";
import { formatLongDate, formatTime, odds, pct, signedPct } from "@/lib/format";
import type { MatchDetail, MarketKey, ValueBet } from "@/lib/types";

const MARKET_TITLES: Record<MarketKey, string> = {
  home: "1 · Domicile",
  draw: "X · Match nul",
  away: "2 · Extérieur",
  over_2_5: "Over 2.5 buts",
  under_2_5: "Under 2.5 buts",
};

function StrengthBar({
  label,
  value,
  color,
  align = "left",
}: {
  label: string;
  value: number;
  color: "emerald" | "sky";
  align?: "left" | "right";
}) {
  // Les indices tournent autour de 1.0 : on centre la barre sur cette valeur.
  const width = Math.min(100, Math.max(6, ((value - 0.4) / 1.2) * 100));
  const fill = color === "emerald" ? "bg-accent" : "bg-info";
  return (
    <div className="space-y-1">
      <div className={`flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-500 ${align === "right" ? "flex-row-reverse" : ""}`}>
        <span>{label}</span>
        <span className="tnum font-mono text-[11px] text-slate-300">{value.toFixed(2)}</span>
      </div>
      <div className={`h-1.5 w-full overflow-hidden rounded-full bg-ink-700 ${align === "right" ? "flex justify-end" : ""}`}>
        <div className={`h-full rounded-full ${fill}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function ProbabilityCard({
  market,
  probability,
  fair,
  book,
  valueBet,
}: {
  market: MarketKey;
  probability: number;
  fair: number | null | undefined;
  book: number | null | undefined;
  valueBet?: ValueBet;
}) {
  const qualifies = Boolean(valueBet?.qualifies);
  return (
    <div
      className={`rounded-xl border p-3.5 transition ${
        qualifies ? "border-accent/40 bg-accent/5" : "border-ink-700/70 bg-ink-900/50"
      }`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {MARKET_TITLES[market]}
      </p>
      <p className="tnum mt-1 font-mono text-2xl font-semibold text-fg">
        {pct(probability)}
      </p>
      <div className="mt-2 space-y-1 text-[11px]">
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Cote juste</span>
          <span className="tnum font-mono text-slate-300">{odds(fair)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Marché</span>
          <span className="tnum font-mono text-slate-300">{odds(book)}</span>
        </div>
        {valueBet ? (
          <div className="flex items-center justify-between border-t border-ink-700/60 pt-1.5">
            <span className="text-slate-500">EV</span>
            <span
              className={`tnum font-mono ${
                valueBet.ev_percent > 0 ? "text-accent" : "text-slate-400"
              }`}
            >
              {signedPct(valueBet.ev_percent)}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function MatchDetailView() {
  const params = useParams<{ id: string }>();
  const matchId = params?.id;

  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiGet<MatchDetail>(`/api/matches/${matchId}`, controller.signal)
      .then((response) => setMatch(response))
      .catch((err: Error) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [matchId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-6 w-40" />
        <div className="card space-y-4 p-6">
          <div className="skeleton h-8 w-2/3" />
          <div className="skeleton h-4 w-1/3" />
          <div className="skeleton h-24 w-full" />
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="skeleton h-32" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="card border-danger/30 bg-danger-soft/20 p-6">
        <p className="text-sm font-semibold text-danger">Analyse indisponible</p>
        <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-slate-300">
          {error ?? "Match introuvable."}
        </p>
        <Link href="/" className="btn-ghost mt-4 inline-flex text-[12px]">
          ← Retour aux matchs
        </Link>
      </div>
    );
  }

  const valueByMarket = (market: MarketKey) =>
    match.value_bets.find((bet) => bet.market === market);

  const eloDelta = match.elo.home - match.elo.away;

  return (
    <div className="space-y-5">
      {/* Fil d'Ariane ---------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href="/"
          className="link-focus inline-flex items-center gap-1.5 rounded text-[12px] text-slate-400 transition hover:text-fg"
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Tous les matchs
        </Link>
        <span className="chip border-ink-600 text-[10px]">
          <CountryFlag country={match.country} size={14} />
          <LeagueBadge code={match.league_code} size={14} />
          {match.league} · {match.country}
        </span>
      </div>

      {/* En-tête comparatif ---------------------------------------------- */}
      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-700/60 px-5 py-3">
          <p className="tnum font-mono text-[11px] uppercase tracking-wide text-slate-500">
            {formatLongDate(match.date)} · {formatTime(match.time)}
          </p>
          <p className="font-mono text-[11px] text-slate-500">
            λ dom. {match.lambdas.home.toFixed(2)} · λ ext. {match.lambdas.away.toFixed(2)}
          </p>
        </div>

        <div className="grid gap-6 px-5 py-6 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <div className="space-y-3">
            <TeamBadge name={match.home_team} logo={match.home_logo} size={48} />
            <p className="text-xl font-semibold leading-tight text-fg">{match.home_team}</p>
            <p className="tnum font-mono text-[11px] uppercase tracking-wider text-slate-500">
              Elo <span className="text-base text-accent">{match.elo.home.toFixed(0)}</span>
            </p>
            <StrengthBar label="Attaque" value={match.forces.home.attack} color="emerald" />
            <StrengthBar label="Défense (bas = meilleur)" value={match.forces.home.defense} color="emerald" />
          </div>

          <div className="flex flex-col items-center gap-2 text-center">
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-slate-600">
              vs
            </span>
            <span
              className={`tnum rounded-md border px-2 py-1 font-mono text-[11px] ${
                Math.abs(eloDelta) < 20
                  ? "border-ink-600 text-slate-400"
                  : eloDelta > 0
                    ? "border-accent/30 bg-accent/5 text-accent"
                    : "border-info/30 bg-info/5 text-info"
              }`}
            >
              {eloDelta > 0 ? "+" : ""}
              {eloDelta.toFixed(0)} Elo
            </span>
            <span className="text-[10px] text-slate-600">avantage terrain inclus</span>
          </div>

          <div className="space-y-3 sm:text-right">
            <div className="sm:flex sm:justify-end">
              <TeamBadge name={match.away_team} logo={match.away_logo} size={48} />
            </div>
            <p className="text-xl font-semibold leading-tight text-fg">{match.away_team}</p>
            <p className="tnum font-mono text-[11px] uppercase tracking-wider text-slate-500">
              Elo <span className="text-base text-info">{match.elo.away.toFixed(0)}</span>
            </p>
            <StrengthBar label="Attaque" value={match.forces.away.attack} color="sky" align="right" />
            <StrengthBar label="Défense (bas = meilleur)" value={match.forces.away.defense} color="sky" align="right" />
          </div>
        </div>

        {match.best_value ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-700/60 bg-accent/[0.04] px-5 py-3">
            <ValueBadge ev={match.best_value.ev_percent} label={match.best_value.label} />
            <p className="text-[11px] text-slate-500">
              Meilleur écart détecté sur ce match — à confronter à votre propre analyse.
            </p>
          </div>
        ) : null}
      </section>

      {/* Marchés 1X2 ------------------------------------------------------ */}
      <section className="grid gap-3 sm:grid-cols-3">
        {(["home", "draw", "away"] as const).map((market) => (
          <ProbabilityCard
            key={market}
            market={market}
            probability={match.probabilities[market]}
            fair={match.fair_odds[market]}
            book={match.odds[market]}
            valueBet={valueByMarket(market)}
          />
        ))}
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {(["over_2_5", "under_2_5"] as const).map((market) => (
          <ProbabilityCard
            key={market}
            market={market}
            probability={market === "over_2_5" ? match.over_2_5 : match.under_2_5}
            fair={match.fair_odds[market]}
            book={match.odds[market]}
            valueBet={valueByMarket(market)}
          />
        ))}
        <div className="rounded-xl border border-ink-700/70 bg-ink-900/50 p-3.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            BTTS · Les deux marquent
          </p>
          <p className="tnum mt-1 font-mono text-2xl font-semibold text-fg">
            {pct(match.btts_yes)}
          </p>
          <div className="mt-2 space-y-1 text-[11px]">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Oui</span>
              <span className="tnum font-mono text-slate-300">{pct(match.btts_yes)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Non</span>
              <span className="tnum font-mono text-slate-300">{pct(match.btts_no)}</span>
            </div>
            <div className="flex items-center justify-between border-t border-ink-700/60 pt-1.5">
              <span className="text-slate-500">Scores probables</span>
              <span className="font-mono text-[10px] text-slate-400">
                {match.top_scores.map((score) => score.score).join(" · ")}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Value bets ------------------------------------------------------- */}
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-fg">Détail des value bets</h2>
            <p className="mt-1 text-[12px] text-slate-500">
              EV = probabilité modèle × cote du marché − 1. Règle Phase 2 : EV ≥ 5 % et cote
              entre 1,40 et 5,00.
            </p>
          </div>
          <span className="chip border-ink-600 text-[10px]">Cotes Bet365 / moyenne marché</span>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="table-base min-w-[560px]">
            <thead>
              <tr>
                <th>Marché</th>
                <th className="text-right">Probabilité</th>
                <th className="text-right">Cote juste</th>
                <th className="text-right">Cote marché</th>
                <th className="text-right">EV</th>
                <th className="text-right">Statut</th>
              </tr>
            </thead>
            <tbody>
              {match.value_bets.map((bet) => (
                <tr key={bet.market} className={bet.qualifies ? "bg-accent/[0.03]" : undefined}>
                  <td className="text-[13px] text-slate-200">{bet.label}</td>
                  <td className="tnum text-right font-mono text-[12px]">
                    {pct(bet.model_probability)}
                  </td>
                  <td className="tnum text-right font-mono text-[12px] text-slate-400">
                    {odds(bet.fair_odds)}
                  </td>
                  <td className="tnum text-right font-mono text-[12px] text-slate-200">
                    {odds(bet.book_odds)}
                  </td>
                  <td
                    className={`tnum text-right font-mono text-[12px] ${
                      bet.ev_percent > 0 ? "text-accent" : "text-slate-500"
                    }`}
                  >
                    {signedPct(bet.ev_percent)}
                  </td>
                  <td className="text-right">
                    {bet.qualifies ? (
                      <span className="rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] uppercase text-accent">
                        Value
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] uppercase text-slate-600">
                        Écarté
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Heatmap + Elo ---------------------------------------------------- */}
      <div className="grid gap-4 xl:grid-cols-2">
        <section className="card p-5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-fg">Probabilités des scores exacts</h2>
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
              Dixon-Coles
            </span>
          </div>
          <div className="mt-4">
            <ScoreHeatmap matrix={match.score_matrix} />
          </div>
        </section>

        <section className="card p-5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-fg">Évolution du classement Elo</h2>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="flex items-center gap-1.5 text-slate-400">
                <span className="h-1.5 w-3 rounded-full bg-accent" /> {match.home_team}
              </span>
              <span className="flex items-center gap-1.5 text-slate-400">
                <span className="h-1.5 w-3 rounded-full bg-info" /> {match.away_team}
              </span>
            </div>
          </div>
          <div className="mt-2">
            <EloChart home={match.elo_history.home} away={match.elo_history.away} />
          </div>
        </section>
      </div>

      {/* Forme avancée (10 derniers matchs) -------------------------------- */}
      {match.form ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <section className="card p-5">
            <h2 className="mb-3 text-sm font-semibold text-fg">
              {match.home_team} · forme sur 10 matchs
            </h2>
            <FormStats form={match.form.home} />
          </section>
          <section className="card p-5">
            <h2 className="mb-3 text-sm font-semibold text-fg">
              {match.away_team} · forme sur 10 matchs
            </h2>
            <FormStats form={match.form.away} />
          </section>
        </div>
      ) : null}

      {/* Effectifs, blessures, compositions, notes ------------------------- */}
      <ExternalContextSection
        external={match.external}
        homeTeam={match.home_team}
        awayTeam={match.away_team}
      />

      {/* Forme récente (5 derniers matchs, détail) -------------------------- */}
      <div className="grid gap-4 xl:grid-cols-2">
        <section className="card p-5">
          <h2 className="mb-3 text-sm font-semibold text-fg">
            {match.recent.home.team} · 5 derniers matchs
          </h2>
          <FormTable
            team={match.recent.home.team}
            matches={match.recent.home.matches}
            summary={match.recent.home.summary}
            accent="home"
          />
        </section>
        <section className="card p-5">
          <h2 className="mb-3 text-sm font-semibold text-fg">
            {match.recent.away.team} · 5 derniers matchs
          </h2>
          <FormTable
            team={match.recent.away.team}
            matches={match.recent.away.matches}
            summary={match.recent.away.summary}
            accent="away"
          />
        </section>
      </div>

      {/* Simulateur -------------------------------------------------------- */}
      <KellySimulator
        valueBets={match.value_bets}
        bankrollDefault={match.kelly.bankroll_default}
        fraction={match.kelly.fraction}
        capPercent={match.kelly.cap_percent}
      />

      <p className="text-[11px] leading-relaxed text-slate-600">
        Les cotes affichées proviennent de Football-Data.co.uk (Bet365, repli sur la moyenne du
        marché). Elles peuvent avoir évolué depuis leur publication. Aucune prédiction ne
        garantit un résultat.
      </p>
    </div>
  );
}
