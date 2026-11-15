"use client";

import { useEffect, useState } from "react";
import CountryLeagueFilter from "@/components/CountryLeagueFilter";
import ProbabilityBar from "@/components/ProbabilityBar";
import ValueBadge from "@/components/ValueBadge";
import { apiGet } from "@/lib/api";
import { formatDate, odds, pct, signedPct } from "@/lib/format";
import { leaguesForCountry } from "@/lib/leagues";
import type {
  HistoryMatch,
  HistoryMatchday,
  HistoryMatchdaysResponse,
  OutcomeKey,
} from "@/lib/types";

const OUTCOME_LABEL: Record<OutcomeKey, string> = { home: "1", draw: "X", away: "2" };
const OUTCOME_NAME: Record<OutcomeKey, string> = {
  home: "Domicile",
  draw: "Nul",
  away: "Extérieur",
};

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card px-4 py-3">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="tnum mt-1 font-mono text-xl font-semibold text-fg">{value}</p>
      {hint ? <p className="mt-0.5 text-[10px] text-slate-600">{hint}</p> : null}
    </div>
  );
}

function MatchRow({ match }: { match: HistoryMatch }) {
  const correctStyle = match.correct
    ? "border-accent/40 bg-accent/10 text-accent"
    : "border-danger/40 bg-danger/10 text-danger";

  return (
    <article className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 truncate text-[15px] font-medium text-fg">
          {match.home_team}
          <span className="tnum mx-1.5 font-mono text-slate-400">
            {match.score.home} – {match.score.away}
          </span>
          {match.away_team}
        </p>
        <span
          className={`shrink-0 rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${correctStyle}`}
        >
          {match.correct ? "Pronostic juste" : "Pronostic manqué"}
        </span>
      </div>

      <ProbabilityBar
        home={match.probabilities.home}
        draw={match.probabilities.draw}
        away={match.probabilities.away}
      />

      <div className="grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
        <div>
          <p className="text-slate-500">Pronostic</p>
          <p className="tnum font-mono text-slate-200">
            {OUTCOME_LABEL[match.predicted]} · {OUTCOME_NAME[match.predicted]}{" "}
            <span className="text-slate-500">({pct(match.predicted_probability, 0)})</span>
          </p>
        </div>
        <div>
          <p className="text-slate-500">Résultat</p>
          <p className="tnum font-mono text-slate-200">
            {OUTCOME_LABEL[match.actual]} · {OUTCOME_NAME[match.actual]}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Brier</p>
          <p className={`tnum font-mono ${match.brier < 0.5 ? "text-accent" : "text-slate-200"}`}>
            {match.brier.toFixed(3)}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Cote du pronostic</p>
          <p className="tnum font-mono text-slate-200">
            {odds(match.odds ? match.odds[match.predicted] : null)}
          </p>
        </div>
      </div>

      {match.best_value ? (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-ink-700/60 pt-2 text-[11px]">
          <span className="text-slate-500">
            Value détecté : <span className="text-slate-300">{match.best_value.label}</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="font-mono text-slate-400">
              cote {odds(match.best_value.book_odds)}
            </span>
            <span
              className={`tnum font-mono ${
                match.best_value.market === match.actual ? "text-accent" : "text-slate-500"
              }`}
            >
              {signedPct(match.best_value.ev_percent)}
            </span>
            <ValueBadge ev={match.best_value.ev_percent} size="sm" />
          </span>
        </div>
      ) : null}
    </article>
  );
}

export default function HistoryView() {
  const [country, setCountry] = useState("ALL");
  const [league, setLeague] = useState("E0");
  const [limit, setLimit] = useState(6);
  const [list, setList] = useState<HistoryMatchdaysResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<HistoryMatchday | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingList(true);
    setError(null);
    setDetail(null);

    apiGet<HistoryMatchdaysResponse>(
      `/api/history/matchdays?league=${league}&limit=${limit}`,
      controller.signal,
    )
      .then((response) => {
        setList(response);
        setSelected(response.matchdays[0]?.date ?? null);
      })
      .catch((err: Error) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoadingList(false));

    return () => controller.abort();
  }, [league, limit]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setLoadingDetail(true);
    setError(null);

    apiGet<HistoryMatchday>(
      `/api/history/matchday?league=${league}&date=${selected}&limit=${limit}`,
      controller.signal,
    )
      .then((response) => setDetail(response))
      .catch((err: Error) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoadingDetail(false));

    return () => controller.abort();
  }, [league, selected, limit]);

  const formatLabel = (from: string, to: string) =>
    from === to ? formatDate(from) : `${formatDate(from)} → ${formatDate(to)}`;

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="chip border-accent/30 bg-accent/5 text-accent">Historique</span>
          <span className="chip">Pronostics vs résultats</span>
        </div>
        <div>
          <h1 className="text-[26px] font-semibold tracking-tight text-fg sm:text-3xl">
            Journées passées — comparaison
          </h1>
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-slate-400">
            Pour chaque journée, les probabilités sont reconstruites{" "}
            <span className="text-slate-200">avant</span> les matchs (ordre chronologique
            strict, aucune fuite de données), puis comparées au résultat réel. Les cotes
            affichées sont celles disponibles dans les données historiques.
          </p>
        </div>
      </header>

      <section className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <CountryLeagueFilter
          country={country}
          league={league}
          onCountryChange={(next) => {
            setCountry(next);
            if (next !== "ALL") {
              setLeague(leaguesForCountry(next)[0]?.code ?? league);
            }
          }}
          onLeagueChange={setLeague}
          allowAllLeagues={false}
        />

        <label className="flex items-center gap-2 text-[12px] text-slate-400">
          Journées affichées
          <select
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
            className="link-focus rounded-lg border border-ink-700/70 bg-ink-900/60 px-2.5 py-1.5 font-mono text-[12px] text-slate-200"
          >
            {[3, 6, 10, 15].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error ? (
        <div className="card border-danger/30 bg-danger-soft/20 p-6">
          <p className="text-sm font-semibold text-danger">Historique indisponible</p>
          <p className="mt-2 text-[13px] text-slate-300">{error}</p>
        </div>
      ) : null}

      {loadingList ? (
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="skeleton h-9 w-28" />
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {(list?.matchdays ?? []).map((matchday) => {
            const active = selected === matchday.date;
            return (
              <button
                key={matchday.date}
                type="button"
                onClick={() => setSelected(matchday.date)}
                aria-pressed={active}
                className={`link-focus rounded-lg border px-3 py-1.5 text-[12px] transition ${
                  active
                    ? "border-accent/40 bg-accent/10 text-accent"
                    : "border-ink-700/70 bg-ink-900/60 text-slate-400 hover:border-ink-600 hover:text-slate-200"
                }`}
              >
                {formatLabel(matchday.date_from, matchday.date_to)}
              </button>
            );
          })}
        </div>
      )}

      {detail ? (
        <>
          <section className="grid gap-3 sm:grid-cols-3">
            <Metric
              label="Précision 1X2"
              value={`${detail.summary.correct}/${detail.summary.count}`}
              hint={`${detail.summary.accuracy_percent}% de pronostics justes`}
            />
            <Metric
              label="Brier moyen"
              value={detail.summary.brier_avg.toFixed(4)}
              hint="0 = parfait · 2 = pire"
            />
            <Metric
              label="Value bets"
              value={`${detail.summary.value_hits}/${detail.summary.value_bets}`}
              hint="gagnés / détectés"
            />
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            {detail.matches.map((match, index) => (
              <MatchRow key={`${match.date}-${match.home_team}-${index}`} match={match} />
            ))}
          </section>
        </>
      ) : loadingDetail ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="skeleton h-40" />
          ))}
        </div>
      ) : null}

      <p className="text-[11px] leading-relaxed text-slate-600">
        Les probabilités sont recalculées avec le même moteur que la page « Matchs »
        (Elo dynamique, Time Decay, Poisson Dixon-Coles calibré), entraîné uniquement sur
        les matchs antérieurs à la journée affichée. Aucun résultat futur n&apos;est utilisé.
      </p>
    </div>
  );
}
