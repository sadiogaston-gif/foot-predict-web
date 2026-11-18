"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { pct, odds, formatDate } from "@/lib/format";
import { leagueByCode } from "@/lib/leagues";
import LeagueBadge from "@/components/LeagueBadge";
import TeamBadge from "@/components/TeamBadge";

interface LeagueRow {
  league: string;
  name: string;
  country: string;
  bets: number;
  wins: number;
  win_rate: number;
  avg_odds: number;
  roi_flat: number;
  roi_kelly: number;
  profit_flat: number;
  profit_kelly: number;
}

interface MarketRow {
  market: string;
  label: string;
  bets: number;
  win_rate: number;
  avg_odds: number;
  roi_flat: number;
  profit_flat: number;
  roi_kelly: number;
  profit_kelly: number;
}

interface BankrollPoint {
  index: number;
  date: string;
  label: string;
  flat: number;
  kelly: number;
}

interface BacktestStats {
  available: boolean;
  season: string;
  warmup_seasons: string[];
  warmup_matches: number;
  matches: number;
  bets: number;
  wins: number;
  win_rate: number;
  avg_odds: number;
  avg_ev: number;
  brier_model: number;
  brier_bookmaker: number;
  brier_baserate: number;
  logloss_model: number;
  accuracy_1x2: number;
  strategy_flat: {
    initial_bankroll: number;
    final_bankroll: number;
    roi_flat: number;
    kelly_fraction: number;
    kelly_cap: number;
  };
  strategy_kelly: {
    initial_bankroll: number;
    final_bankroll: number;
    roi_flat: number;
    kelly_fraction: number;
    kelly_cap: number;
  };
  by_league: LeagueRow[];
  by_market: MarketRow[];
  bankroll_curve: BankrollPoint[];
  params: {
    ev_threshold: number;
    min_odds: number;
    max_odds: number;
    initial_bankroll: number;
    kelly_fraction: number;
    kelly_cap: number;
  };
}

export default function BacktestPage() {
  const [stats, setStats] = useState<BacktestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [season, setSeason] = useState("2526");
  const [leagueFilter, setLeagueFilter] = useState("ALL");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiGet<BacktestStats>(
        `/api/backtest/stats?season=${season}`
      );
      setStats(response);
    } catch (err: any) {
      setError(err?.message ?? "Erreur lors du chargement du backtest");
    } finally {
      setLoading(false);
    }
  }, [season]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="flex h-8 w-8 rounded-full border-4 border-ink-700 border-t-accent animate-spin" />
        <p className="mt-4 text-sm text-slate-400">Chargement du backtest...</p>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center px-4 sm:px-10">
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

  const filteredLeagues = leagueFilter === "ALL"
    ? stats.by_league
    : stats.by_league.filter((l) => l.league === leagueFilter);

  const leagues = stats.by_league.map((l) => ({
    code: l.league,
    name: leagueByCode(l.league)?.name || l.league,
    country: leagueByCode(l.league)?.country || "",
  }));

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col lg:flex-row items-start justify-between gap-4 px-4">
        <div>
          <h1 className="text-[24px] font-semibold tracking-tight text-fg sm:text-3xl">
            Backtest & Transparence
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Résultats réels du modèle Elo sur les saisons passées. Tous les matchs sont
            rejoués chronologiquement pour simuler les prédictions telles qu'elles
            auraient été faites en temps réel.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={season}
            onChange={(e) => setSeason(e.target.value)}
            className="rounded-lg border border-ink-700/70 bg-ink-800/60 px-3 py-2 text-[12px] text-slate-300 focus:outline-none focus:ring-2 focus:ring-accent/50"
          >
            {stats.warmup_seasons.map((s) => (
              <option key={s} value={s}>
                Saison {s.slice(0, 2)}/{s.slice(2, 4)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 px-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Matchs analysés
          </span>
          <span className="tnum font-mono text-lg font-semibold text-fg mt-1 block">
            {stats.matches.toLocaleString()}
          </span>
        </div>
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Paris simulés
          </span>
          <span className="tnum font-mono text-lg font-semibold text-fg mt-1 block">
            {stats.bets.toLocaleString()}
          </span>
        </div>
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Taux de réussite
          </span>
          <span className="tnum font-mono text-lg font-semibold text-fg mt-1 block">
            {pct(stats.win_rate)}
          </span>
        </div>
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Brier Score
          </span>
          <span className="tnum font-mono text-lg font-semibold text-fg mt-1 block">
            {stats.brier_model.toFixed(3)}
          </span>
        </div>
      </div>

      {/* Results cards */}
      <div className="grid gap-4 px-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            ROI Flat (Mise fixe)
          </span>
          <span className={`tnum font-mono text-lg font-semibold ${stats.strategy_flat.roi_flat >= 0 ? "text-emerald-400" : "text-danger"}`} mt-1 block>
            {pct(stats.strategy_flat.roi_flat)}
          </span>
          <span className="text-[10px] text-slate-400 mt-1 block">
            Bankroll: {stats.strategy_flat.final_bankroll.toFixed(2)} €
          </span>
        </div>
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            ROI Kelly
          </span>
          <span className={`tnum font-mono text-lg font-semibold ${stats.strategy_kelly.roi_flat >= 0 ? "text-emerald-400" : "text-danger"}`} mt-1 block>
            {pct(stats.strategy_kelly.roi_flat)}
          </span>
          <span className="text-[10px] text-slate-400 mt-1 block">
            Bankroll: {stats.strategy_kelly.final_bankroll.toFixed(2)} €
          </span>
        </div>
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Cote moyenne
          </span>
          <span className="tnum font-mono text-lg font-semibold text-fg mt-1 block">
            {stats.avg_odds.toFixed(2)}
          </span>
        </div>
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            EV moyen
          </span>
          <span className={`tnum font-mono text-lg font-semibold ${stats.avg_ev >= 0 ? "text-emerald-400" : "text-slate-300"}`} mt-1 block>
            {pct(stats.avg_ev)}
          </span>
        </div>
      </div>

      {/* Par championnat */}
      <div className="card p-4">
        <h2 className="text-[13px] font-semibold uppercase tracking-wider text-slate-500 mb-4">
          Résultats par championnat
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="border-b border-ink-700/60">
                <th className="text-left pb-2 text-slate-500">Championnat</th>
                <th className="text-right pb-2 text-slate-500">Matchs</th>
                <th className="text-right pb-2 text-slate-500">Paris</th>
                <th className="text-right pb-2 text-slate-500">Win Rate</th>
                <th className="text-right pb-2 text-slate-500">ROI Flat</th>
                <th className="text-right pb-2 text-slate-500">ROI Kelly</th>
              </tr>
            </thead>
            <tbody>
              {filteredLeagues.map((row) => (
                <tr key={row.league} className="border-b border-ink-700/40">
                  <td className="pb-1">
                    <div className="flex items-center gap-2">
                      <LeagueBadge code={row.league} size={12} />
                      <span className="text-slate-300">{row.name}</span>
                    </div>
                  </td>
                  <td className="pb-1 text-right text-slate-300">{row.matches}</td>
                  <td className="pb-1 text-right text-slate-300">{row.bets}</td>
                  <td className="pb-1 text-right text-slate-300">{pct(row.win_rate)}</td>
                  <td className={`pb-1 text-right font-mono ${row.roi_flat >= 0 ? "text-emerald-400" : "text-danger"}`}>
                    {pct(row.roi_flat)}
                  </td>
                  <td className={`pb-1 text-right font-mono ${row.roi_kelly >= 0 ? "text-emerald-400" : "text-danger"}`}>
                    {pct(row.roi_kelly)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Par marché */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Résultats par marché
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="border-b border-ink-700/60">
                <th className="text-left pb-2 text-slate-500">Marché</th>
                <th className="text-right pb-2 text-slate-500">Paris</th>
                <th className="text-right pb-2 text-slate-500">Win Rate</th>
                <th className="text-right pb-2 text-slate-500">ROI Flat</th>
                <th className="text-right pb-2 text-slate-500">ROI Kelly</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_market.map((row) => (
                <tr key={row.market} className="border-b border-ink-700/40">
                  <td className="pb-1 text-slate-300">{row.label}</td>
                  <td className="pb-1 text-right text-slate-300">{row.bets}</td>
                  <td className="pb-1 text-right text-slate-300">{pct(row.win_rate)}</td>
                  <td className={`pb-1 text-right font-mono ${row.roi_flat >= 0 ? "text-emerald-400" : "text-danger"}`}>
                    {pct(row.roi_flat)}
                  </td>
                  <td className={`pb-1 text-right font-mono ${row.roi_kelly >= 0 ? "text-emerald-400" : "text-danger"}`}>
                    {pct(row.roi_kelly)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bankroll curve */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Courbe de bankroll
          </span>
        </div>
        <div className="h-64 w-full overflow-x-auto border-b border-ink-700/70 pb-2">
          <div className="flex items-end gap-1 h-full min-w-[calc(100vw-2rem)]">
            {stats.bankroll_curve.map((point) => (
              <div
                key={point.index}
                className="flex flex-col items-center gap-1"
                style={{ height: `${(point.flat / stats.strategy_flat.initial_bankroll) * 100}%` }}
              >
                <div className="w-1 bg-accent rounded-t" />
                <span className="text-[9px] text-slate-500 rotate-[-45deg]">{point.label}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-slate-500 mt-2">
            <span>Bankroll initiale: {stats.strategy_flat.initial_bankroll} €</span>
            <span>Flat: {stats.strategy_flat.final_bankroll.toFixed(2)} €</span>
            <span>Kelly: {stats.strategy_kelly.final_bankroll.toFixed(2)} €</span>
          </div>
        </div>
      </div>
    </div>
  );
}
