"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TeamBadge from "@/components/TeamBadge";
import { apiGet } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";
import type { MatchSummary } from "@/lib/types";

interface LiveMatch {
  id: string;
  home_team: string;
  away_team: string;
  home_logo?: string | null;
  away_logo?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  minute?: number | null;
  status: "scheduled" | "live" | "finished" | "postponed";
  league_code: string;
  league: string;
  date: string;
}

export default function LivePage() {
  const [matches, setMatches] = useState<LiveMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [filterLeague, setFilterLeague] = useState<string>("ALL");

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const response = await apiGet<MatchSummary[]>(
          "/api/matches/live",
          signal,
        );
        // map vers LiveMatch
        const liveMatches: LiveMatch[] = (response as any[]).map((m: any) => ({
          id: m.id,
          home_team: m.home_team,
          away_team: m.away_team,
          home_logo: m.home_logo,
          away_logo: m.away_logo,
          home_score: m.home_score,
          away_score: m.away_score,
          minute: m.minute,
          status: m.status,
          league_code: m.league_code,
          league: m.league,
          date: m.date,
        }));
        setMatches(liveMatches);
      } catch (err: any) {
        if (err.name !== "AbortError") setError(err?.message ?? "Erreur API");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const filtered = matches.filter((m) => {
    if (filterStatus !== "ALL" && m.status !== filterStatus) return false;
    if (filterLeague !== "ALL" && m.league_code !== filterLeague) return false;
    return true;
  });

  const leagues = [...new Set(matches.map((m) => m.league_code))].map((code) => {
    const match = matches.find((m) => m.league_code === code);
    return { code, name: match?.league || code };
  });

  const statusColor = (status: string) => {
    switch (status) {
      case "live": return "text-emerald-400";
      case "finished": return "text-slate-400";
      case "scheduled": return "text-slate-400";
      case "postponed": return "text-amber-400";
      default: return "text-slate-500";
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-8 w-8 rounded-full border-4 border-ink-700 border-t-accent animate-spin" />
          <p className="text-sm text-slate-400">Chargement des matchs en direct...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-danger text-sm font-semibold">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 btn-ghost link-focus text-[12px]"
        >
          Réessayer
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row items-start justify-between gap-4 px-4">
        <div>
          <h1 className="text-[24px] font-semibold tracking-tight text-fg sm:text-3xl">
            Matchs en Direct
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Résultats et affiches en temps réel depuis les données publiques.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={filterLeague}
            onChange={(e) => setFilterLeague(e.target.value)}
            className="rounded-lg border border-ink-700/70 bg-ink-800/60 px-3 py-2 text-[12px] text-slate-300 focus:outline-none focus:ring-2 focus:ring-accent/50"
          >
            <option value="ALL">Tous les championnats</option>
            {leagues.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="rounded-lg border border-ink-700/70 bg-ink-800/60 px-3 py-2 text-[12px] text-slate-300 focus:outline-none focus:ring-2 focus:ring-accent/50"
          >
            <option value="ALL">Tous les statuts</option>
            <option value="live">En direct</option>
            <option value="finished">Terminés</option>
            <option value="scheduled">À venir</option>
            <option value="postponed">Reportés</option>
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center px-4 sm:px-10">
          <p className="text-sm font-medium text-slate-300">
            Aucun match ne correspond aux filtres.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 px-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((match) => (
            <div key={match.id} className="card p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <span className="chip border-ink-600 bg-ink-800 text-[10px] text-slate-300">
                  {match.league}
                </span>
                <span className={`text-[11px] font-mono ${statusColor(match.status)}`}>
                  {match.status === "live" ? `🔴 ${match.minute}'` : match.status}
                </span>
              </div>

              <div className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-2">
                  <TeamBadge name={match.home_team} logo={match.home_logo} size={20} />
                  <span className="truncate text-[15px] font-medium text-slate-300">
                    {match.home_team}
                  </span>
                </span>
                {match.status === "live" || match.status === "finished" ? (
                  <div className="flex items-center gap-2 text-[20px] font-mono font-bold text-fg">
                    {match.home_score ?? "-"}
                    <span className="mx-1 text-slate-500">-</span>
                    {match.away_score ?? "-"}
                  </div>
                ) : (
                  <span className="tnum font-mono text-[11px] text-slate-500">
                    {formatDate(match.date)} · {formatTime(match.time)}
                  </span>
                )}
              </div>
              <span className="flex min-w-0 items-center gap-2">
                <TeamBadge name={match.away_team} logo={match.away_logo} size={20} />
                <span className="truncate text-[15px] font-medium text-slate-300">
                  {match.away_team}
                </span>
              </div>

              {match.status === "live" && (
                <div className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-ink-700">
                  <div
                    className="h-full bg-accent transition-[width] duration-1000"
                    style={{ width: `${Math.min(match.minute ?? 0, 90) / 90 * 100}%` }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
