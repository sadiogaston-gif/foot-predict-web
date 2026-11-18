"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import LeagueBadge from "@/components/LeagueBadge";
import { apiGet } from "@/lib/api";
import { formatDate, pct } from "@/lib/format";
import type { BacktestStats, LeagueRow as TypesLeagueRow } from "@/lib/types";

interface LeagueRow {
  league: string;
  name: string;
  matches: number;
  bets: number;
  wins: number;
  win_rate: number;
  roi_flat: number;
  roi_kelly: number;
}

interface BacktestResponse {
  stats: BacktestStats;
  by_league: TypesLeagueRow[];
  by_market: { market: string; label: string; bets: number; win_rate: number; avg_odds: number; roi_flat: number; profit_flat: number; roi_kelly: number; profit_kelly: number }[];
  bankroll_curve: { index: number; date: string; label: string; flat: number; kelly: number }[];
  params: { ev_threshold: number; min_odds: number; max_odds: number; initial_bankroll: number; kelly_fraction: number; kelly_cap: number };
  generated_at: string;
  total_bets_recorded: number;
}

export default function BacktestPage() {
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const league = searchParams.get("league") || "E0";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiGet<BacktestResponse>(`/api/backtest/${league}`);
      setData(response);
    } catch (err: any) {
      setError(err?.message ?? "Échec du chargement du backtest");
    } finally {
      setLoading(false);
    }
  }, [league]);

  useEffect(() => {
    load();
  }, [load]);

  const stats = data?.stats;
  const filteredLeagues: LeagueRow[] = data?.by_league.map((l: TypesLeagueRow) => ({
    league: l.league,
    name: l.league,
    matches: l.bets, // Type LeagueRow from types.ts doesn't have matches, use bets as proxy
    bets: l.bets,
    wins: l.wins || 0,
    win_rate: l.win_rate,
    roi_flat: l.roi_flat,
    roi_kelly: l.roi_kelly,
  })) || [];

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-8 w-8 rounded-full border-4 border-ink-700 border-t-accent animate-spin" />
          <p className="text-sm text-slate-400">Chargement du backtest...</p>
        </div>
      </div>
    );
  }

  if (error) {
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

  if (!stats) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center px-4 sm:px-10">
        <p className="text-slate-400 text-sm">Aucune donnée de backtest disponible pour ce championnat.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col lg:flex-row items-start justify-between gap-4">
        <div>
          <Link href="/" className="link-focus text-[11px] font-medium text-accent/80 hover:text-accent">
            ← Retour à l'accueil
          </Link>
          <h1 className="text-[24px] font-semibold tracking-tight text-fg sm:text-3xl mt-2">
            Backtest — {league}
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Simulation sur l'historique : {stats.matches} matchs, {stats.bets} paris qualifiés.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={league}
            onChange={(e) => window.location.href = `/backtest?league=${e.target.value}`}
            className="rounded-lg border border-ink-700/70 bg-ink-800/60 px-3 py-2 text-[12px] text-slate-300 focus:outline-none focus:ring-2 focus:ring-accent/50"
          >
            <option value="E0">Premier League (Angleterre)</option>
            <option value="E1">Championship (Angleterre)</option>
            <option value="F1">Ligue 1 (France)</option>
            <option value="F2">Ligue 2 (France)</option>
            <option value="D1">Bundesliga (Allemagne)</option>
            <option value="D2">2. Bundesliga (Allemagne)</option>
            <option value="I1">Serie A (Italie)</option>
            <option value="I2">Serie B (Italie)</option>
            <option value="SP1">LaLiga (Espagne)</option>
            <option value="SP2">Segunda División (Espagne)</option>
            <option value="P1">Primeira Liga (Portugal)</option>
            <option value="P2">Liga Portugal 2 (Portugal)</option>
            <option value="N1">Eredivisie (Pays-Bas)</option>
            <option value="B1">Jupiler Pro League (Belgique)</option>
            <option value="T1">Süper Lig (Turquie)</option>
            <option value="T2">TFF 1. Lig (Turquie)</option>
            <option value="SC0">Premiership (Écosse)</option>
            <option value="G1">Super League (Grèce)</option>
          </select>
        </div>
      </div>

      {/* Statistiques globales */}
      <div className="grid gap-4 px-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Précision 1X2
          </span>
          <span className="tnum font-mono text-lg font-semibold text-fg mt-1 block">
            {pct(stats.accuracy_1x2)}
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
          <span className={`tnum font-mono text-lg font-semibold ${stats.strategy_flat.roi_percent >= 0 ? "text-emerald-400" : "text-danger"}`} style={{display: "block", marginTop: "0.25rem"}}>
            {pct(stats.strategy_flat.roi_percent)}
          </span>
          <span className="text-[10px] text-slate-400 mt-1 block">
            Bankroll: {stats.strategy_flat.final_bankroll.toFixed(2)} €
          </span>
        </div>
        <div className="card p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            ROI Kelly
          </span>
          <span className={`tnum font-mono text-lg font-semibold ${stats.strategy_kelly.roi_percent >= 0 ? "text-emerald-400" : "text-danger"}`} style={{display: "block", marginTop: "0.25rem"}}>
            {pct(stats.strategy_kelly.roi_percent)}
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
          <span className={`tnum font-mono text-lg font-semibold ${stats.avg_ev >= 0 ? "text-emerald-400" : "text-slate-300"}`} style={{display: "block", marginTop: "0.25rem"}}>
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
              {filteredLeagues.map((row: LeagueRow) => (
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
            {stats.bankroll_curve.map((point: { index: number; flat: number; label: string }) => (
              <div
                key={point.index}
                className="flex flex-col items-center gap-1"
                style={{ height: `${(point.flat / (stats.strategy_flat.final_bankroll - stats.strategy_flat.profit)) * 100}%` }}
              >
                <div className="w-1 bg-accent rounded-t" />
                <span className="text-[9px] text-slate-500 rotate-[-45deg]">{point.label}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-slate-500 mt-2">
            <span>Bankroll initiale: {stats.strategy_flat.final_bankroll - stats.strategy_flat.profit} €</span>
            <span>Flat: {stats.strategy_flat.final_bankroll.toFixed(2)} €</span>
            <span>Kelly: {stats.strategy_kelly.final_bankroll.toFixed(2)} €</span>
          </div>
        </div>
      </div>
    </div>
  );
}