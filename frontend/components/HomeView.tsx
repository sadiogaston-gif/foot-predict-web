"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import CountryLeagueFilter from "@/components/CountryLeagueFilter";
import MatchCard from "@/components/MatchCard";
import ValueBadge from "@/components/ValueBadge";
import { formatDate } from "@/lib/format";
import { leaguesForCountry } from "@/lib/leagues";
import type { UpcomingResponse } from "@/lib/types";
import { getMatches, getStoredLeagues } from "@/lib/db";
import { syncUpcoming } from "@/lib/sync";

function SkeletonCard() {
  return (
    <div className="card space-y-4 p-4">
      <div className="flex justify-between">
        <div className="skeleton h-5 w-24" />
        <div className="skeleton h-4 w-20" />
      </div>
      <div className="space-y-2">
        <div className="skeleton h-5 w-2/3" />
        <div className="skeleton h-5 w-1/2" />
      </div>
      <div className="skeleton h-2.5 w-full" />
      <div className="skeleton h-16 w-full" />
      <div className="skeleton h-4 w-40" />
    </div>
  );
}

export default function HomeView() {
  const [country, setCountry] = useState("ALL");
  const [league, setLeague] = useState("ALL");
  const [valueOnly, setValueOnly] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [data, setData] = useState<UpcomingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"cache" | "api" | null>(null);

  const handleCountryChange = (nextCountry: string) => {
    setCountry(nextCountry);
    if (nextCountry === "ALL") {
      setLeague("ALL");
      return;
    }
    setLeague(leaguesForCountry(nextCountry)[0]?.code ?? "ALL");
  };

  /** Affiche immédiatement les affiches déjà stockées localement (hors-ligne). */
  const loadCached = useCallback(async () => {
    const leagues = await getStoredLeagues();
    // Si aucun championnat n'est encore en local, on démarre avec une liste vide
    // et on laisse la synchronisation remplir le cache.
    if (leagues.length === 0) {
      setData({ matches: [], count: 0, slate: { source: "cache", projected: false, note: "Aucune donnée en local." } });
      setLoading(false);
      return;
    }
    const matches = await getMatches({
      league: league === "ALL" ? undefined : league,
    });
    setData({
      matches,
      count: matches.length,
      slate: {
        source: "cache",
        projected: false,
        note: "Données locales (hors-ligne) — synchronisez pour mettre à jour.",
        first_date: null,
        last_date: null,
      },
    });
    setLoading(false);
  }, [league]);

  /** Synchronise avec le backend et met à jour l'affichage. */
  const syncAndUpdate = useCallback(
    async (signal: AbortSignal) => {
      setError(null);
      try {
        const result = await syncUpcoming({
          league: league === "ALL" ? undefined : league,
          valueOnly,
        });
        setSource(result.source);
        setData({
          matches: result.matches,
          count: result.count,
          slate: {
            source: result.source,
            projected: false,
            note: result.error
              ? `Réseau indisponible — affichage du cache local (${result.count} affiches).`
              : "Données à jour depuis le backend.",
            refreshed_at: result.syncedAt,
            first_date: null,
            last_date: null,
          },
        });
        if (result.error) setError(result.error);
      } catch (err: any) {
        if (signal?.aborted) return;
        setError(err?.message ?? "Échec du chargement des affiches.");
      } finally {
        setLoading(false);
      }
    },
    [league, valueOnly],
  );

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      await loadCached();
      // Synchronise en arrière-plan (ne bloque pas l'affichage).
      await syncAndUpdate(signal);
    },
    [loadCached, syncAndUpdate],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, reloadKey]);

  const matches = data?.matches ?? [];
  const bestValue = useMemo(() => {
    const values = matches
      .map((match) => match.best_value)
      .filter((value): value is NonNullable<typeof value> => value !== null);
    if (values.length === 0) return null;
    return values.reduce((best, current) =>
      current.ev_percent > best.ev_percent ? current : best,
    );
  }, [matches]);

  const slate = data?.slate;
  const dateRange =
    slate?.first_date && slate?.last_date
      ? slate.first_date === slate.last_date
        ? formatDate(slate.first_date)
        : `${formatDate(slate.first_date)} → ${formatDate(slate.last_date)}`
      : "—";

  return (
    <div className="space-y-8">
      {/* ---------------------------------------------------------------- */}
      {/* En-tête                                                          */}
      {/* ---------------------------------------------------------------- */}
      <header className="space-y-3 relative z-30">
        <div className="flex flex-wrap items-center gap-2">
          <span className="chip border-accent/30 bg-accent/5 text-accent">
            Saison en cours
          </span>
          <span className="chip">1X2 · Over 2.5 · BTTS</span>
          <span className="chip">13 championnats</span>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-fg sm:text-3xl">
              Matchs &amp; Value Bets
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-400">
              Probabilités issues du moteur Elo dynamique + Time Decay + Poisson ajusté
              Dixon-Coles, comparées aux cotes du marché. Un value bet est signalé lorsque
              l'espérance de gain dépasse <span className="font-mono text-slate-200">+5 %</span>.
              Les données sont stockées localement sur le téléphone et se mettent à jour
              automatiquement lorsque le réseau est disponible.
            </p>
          </div>
          <div className="tnum text-right font-mono text-[11px] leading-relaxed text-slate-500">
            <p>Journée : {dateRange}</p>
            <p>
              {data ? `${data.count} rencontres` : "chargement…"} (
              {source === "api" ? "en ligne" : source === "cache" ? "cache local" : "—"})
            </p>
          </div>
        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Bandeau source de données                                        */}
      {/* ---------------------------------------------------------------- */}
      {slate?.note ? (
        <div
          className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${
            source === "cache"
              ? "border-warn/25 bg-warn-soft/40"
              : "border-accent/25 bg-accent-soft/20"
          }`}
        >
          <svg
            viewBox="0 0 24 24"
            className="mt-0.5 h-4 w-4 shrink-0"
            fill="none"
            stroke={source === "cache" ? "currentColor" : "currentColor"}
            strokeWidth={1.8}
          >
            <path
              d="M12 9v4m0 4h.01M10.3 3.9 2.4 17a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className={`text-[12px] leading-relaxed ${
            source === "cache" ? "text-warn/90" : "text-accent/90"
          }`}>
            <span className="font-semibold uppercase tracking-wide">
              {source === "cache" ? "Source des affiches — cache local" : "Source des affiches — backend"}
            </span>
            {` — ${slate.note}`}
          </p>
        </div>
      ) : null}

      {/* ---------------------------------------------------------------- */}
      {/* Filtres                                                          */}
      {/* ---------------------------------------------------------------- */}
      <section className="flex flex-col lg:flex-row gap-4 px-4 md:px-6">
        <CountryLeagueFilter
          country={country}
          league={league}
          onCountryChange={handleCountryChange}
          onLeagueChange={setLeague}
        />
        <div className="flex flex-col lg:flex-row gap-2 w-full lg:w-auto">
          <div className="flex items-center gap-3">
            <button
              type="button"
              role="switch"
              aria-checked={valueOnly}
              onClick={() => setValueOnly((current) => !current)}
              className="link-focus group flex items-center gap-2.5 rounded-xl border border-ink-700/70 bg-ink-900/60 px-3 py-2 transition hover:border-ink-600"
            >
              <span
                className={`relative h-5 w-9 rounded-full transition ${
                  valueOnly ? "bg-accent/90" : "bg-ink-600"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${
                    valueOnly ? "left-[18px]" : "left-0.5"
                  }`}
                />
              </span>
              <span
                className={`text-[12px] font-medium ${
                  valueOnly ? "text-accent" : "text-slate-400 group-hover:text-slate-200"
                }`}
              >
                Value bets uniquement
              </span>
            </button>

            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              disabled={loading}
              className="btn-ghost link-focus flex items-center gap-2 text-[12px] disabled:opacity-60"
              title="Rafraîchir les affiches et les prédictions"
            >
              <svg
                viewBox="0 0 24 24"
                className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                fill="none"
                stroke="currentColor"
                strokeWidth={1.8}
              >
                <path
                  d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Actualiser
            </button>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Bandeau de synthèse                                              */}
      {/* ---------------------------------------------------------------- */}
      {!loading && !error && matches.length > 0 ? (
        <section className="grid gap-3 sm:grid-cols-3">
          <div className="card flex items-center justify-between px-4 py-3">
            <span className="text-[11px] uppercase tracking-wider text-slate-500">
              Rencontres
            </span>
            <span className="tnum font-mono text-lg font-semibold text-fg">
              {matches.length}
            </span>
          </div>
          <div className="card flex items-center justify-between px-4 py-3">
            <span className="text-[11px] uppercase tracking-wider text-slate-500">
              Value bets 1X2
            </span>
            <span className="tnum font-mono text-lg font-semibold text-accent">
              {matches.filter((match) => match.is_value_bet).length}
            </span>
          </div>
          <div className="card flex items-center justify-between gap-3 px-4 py-3">
            <span className="text-[11px] uppercase tracking-wider text-slate-500">
              Meilleure value
            </span>
            {bestValue ? (
              <span className="flex items-center gap-2">
                <span className="tnum font-mono text-sm text-slate-400">
                  {bestValue.model_probability.toFixed(0)}%
                </span>
                <ValueBadge ev={bestValue.ev_percent} size="sm" />
              </span>
            ) : (
              <span className="font-mono text-sm text-slate-500">—</span>
            )}
          </div>
        </section>
      ) : null}

      {/* ---------------------------------------------------------------- */}
      {/* Erreur                                                           */}
      {/* ---------------------------------------------------------------- */}
      {error ? (
        <div className="card border-danger/30 bg-danger-soft/20 p-6">
          <p className="text-sm font-semibold text-danger">
            {source === "cache" ? "Réseau indisponible" : "API indisponible"}
          </p>
          <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-slate-300">
            {error}
            {source === "cache" ? " — Les données en cache local sont affichées." : ""}
          </p>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className="btn-ghost mt-4 text-[12px]"
          >
            Réessayer
          </button>
        </div>
      ) : null}

      {/* ---------------------------------------------------------------- */}
      {/* Grille de matchs                                                 */}
      {/* ---------------------------------------------------------------- */}
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : null}

      {!loading && !error && matches.length === 0 ? (
        <div className="card flex flex-col items-center justify-center px-6 py-16 text-center">
          <p className="text-sm font-medium text-slate-300">
            Aucun match ne correspond aux filtres.
          </p>
          <p className="mt-1 text-[12px] text-slate-500">
            Essayez un autre championnat ou désactivez le filtre « value bets
            uniquement ».
          </p>
        </div>
      ) : null}

      {!loading && !error && matches.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {matches.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
