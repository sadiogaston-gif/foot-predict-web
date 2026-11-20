"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import LeagueBadge from "@/components/LeagueBadge";
import { apiGet } from "@/lib/api";
import { pct } from "@/lib/format";
import { LEAGUES } from "@/lib/leagues";
import type { SimulationResponse } from "@/lib/types";

const SIM_LEAGUES = ["E0", "E1", "F1", "D1", "I1", "SP1", "P1", "N1"];

function positionColor(position: number, total: number): string {
  if (position === 1) return "text-accent font-semibold";
  if (position <= 4) return "text-emerald-400";
  if (position > total - 3) return "text-danger";
  return "text-slate-300";
}

function SimulationContent() {
  const searchParams = useSearchParams();
  const league = searchParams.get("league") || "E0";
  const [data, setData] = useState<SimulationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiGet<SimulationResponse>(
        `/api/simulation/${league}?scenarios=10000`,
      );
      setData(response);
    } catch (err: any) {
      setError(err?.message ?? "Échec du chargement de la simulation");
    } finally {
      setLoading(false);
    }
  }, [league]);

  useEffect(() => {
    load();
  }, [load]);

  const leagueName = LEAGUES.find((l) => l.code === league)?.name ?? league;

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      {/* En-tête */}
      <div className="flex flex-col lg:flex-row items-start justify-between gap-4">
        <div>
          <Link href="/" className="link-focus text-[11px] font-medium text-accent/80 hover:text-accent">
            ← Retour aux matchs
          </Link>
          <h1 className="text-[24px] font-semibold tracking-tight text-fg sm:text-3xl mt-2">
            Simulateur de classement
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Projection du classement final après 10 000 scénarios Monte Carlo, à partir du
            calendrier restant et des probabilités du modèle.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[11px] text-slate-500" htmlFor="sim-league">
            Championnat
          </label>
          <select
            id="sim-league"
            value={league}
            onChange={(e) => (window.location.href = `/simulation?league=${e.target.value}`)}
            className="rounded-lg border border-ink-700/70 bg-ink-800/60 px-3 py-2 text-[12px] text-slate-300 focus:outline-none focus:ring-2 focus:ring-accent/50"
          >
            {SIM_LEAGUES.map((code) => {
              const info = LEAGUES.find((l) => l.code === code);
              return (
                <option key={code} value={code}>
                  {info?.name ?? code} ({info?.country ?? code})
                </option>
              );
            })}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="flex h-8 w-8 rounded-full border-4 border-ink-700 border-t-accent animate-spin" />
          <p className="mt-4 text-sm text-slate-400">Simulation de 10 000 scénarios en cours…</p>
        </div>
      ) : error ? (
        <div className="card border-danger/30 bg-danger-soft/20 p-6 text-center">
          <p className="text-sm font-semibold text-danger">{error}</p>
          <button onClick={() => window.location.reload()} className="btn-ghost mt-4 text-[12px]">
            Réessayer
          </button>
        </div>
      ) : !data?.available ? (
        <div className="card p-6 text-center">
          <p className="text-sm text-slate-400">{data?.reason ?? "Simulation indisponible."}</p>
        </div>
      ) : (
        <>
          {/* KPI de contexte */}
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="card flex flex-col items-center justify-center px-4 py-3">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">Scénarios</span>
              <span className="tnum font-mono text-lg font-semibold text-fg">
                {(data.scenarios ?? 0).toLocaleString("fr-FR")}
              </span>
            </div>
            <div className="card flex flex-col items-center justify-center px-4 py-3">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">Journée actuelle</span>
              <span className="tnum font-mono text-lg font-semibold text-fg">{data.current_matchday}</span>
            </div>
            <div className="card flex flex-col items-center justify-center px-4 py-3">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">Matchs restants</span>
              <span className="tnum font-mono text-lg font-semibold text-fg">{data.remaining_matches}</span>
            </div>
            <div className="card flex flex-col items-center justify-center px-4 py-3">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">Équipes</span>
              <span className="tnum font-mono text-lg font-semibold text-fg">{data.teams}</span>
            </div>
          </div>

          {/* Légende des zones */}
          <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-accent" /> Champion ({data.title_spots})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400" /> Top {data.top4_spots} (Ligue des Champions)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-danger" /> Relégation ({data.relegation_spots})
            </span>
          </div>

          {/* Tableau projeté */}
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[720px] text-[11px]">
              <thead>
                <tr className="border-b border-ink-700/60 text-[10px] uppercase tracking-wider text-slate-500">
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Équipe</th>
                  <th className="px-3 py-2 text-right">Pts actuels</th>
                  <th className="px-3 py-2 text-right">Pts projetés</th>
                  <th className="px-3 py-2 text-right">Pos. moy.</th>
                  <th className="px-3 py-2 text-right">Titre</th>
                  <th className="px-3 py-2 text-right">Top {data.top4_spots}</th>
                  <th className="px-3 py-2 text-right">Relégation</th>
                  <th className="px-3 py-2 text-left">Distribution des positions</th>
                </tr>
              </thead>
              <tbody>
                {(data.standings ?? []).map((row, index) => {
                  const total = data.teams ?? 20;
                  return (
                    <tr key={row.team} className="border-b border-ink-700/40 hover:bg-ink-800/30">
                      <td className={`px-3 py-2 font-mono ${positionColor(index + 1, total)}`}>
                        {index + 1}
                      </td>
                      <td className="px-3 py-2">
                        <span className="flex items-center gap-2">
                          <LeagueBadge code={league} size={14} />
                          <span className="font-medium text-slate-200">{row.team}</span>
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-400">{row.current_points}</td>
                      <td className="px-3 py-2 text-right font-mono font-semibold text-fg">
                        {row.projected_points.toFixed(1)}
                      </td>
                      <td className={`px-3 py-2 text-right font-mono ${positionColor(Math.round(row.avg_position), total)}`}>
                        {row.avg_position.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-accent">
                        {row.title_probability > 0.05 ? `${row.title_probability.toFixed(1)}%` : "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-emerald-400">
                        {row.top4_probability.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-danger">
                        {row.relegation_probability > 0.05 ? `${row.relegation_probability.toFixed(1)}%` : "—"}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex h-3 w-32 items-end gap-[1px]" title="Distribution des positions finales">
                          {row.position_probabilities.slice(0, total).map((p, pos) => (
                            <div
                              key={pos}
                              className="flex-1 rounded-sm"
                              style={{
                                height: `${Math.max(2, p)}%`,
                                backgroundColor:
                                  pos === 0 ? "#00e08a" : pos < 4 ? "rgba(52,211,153,0.6)" : pos >= total - 3 ? "rgba(239,68,68,0.6)" : "rgba(100,116,139,0.4)",
                              }}
                              title={`${pos + 1}e : ${p.toFixed(1)}%`}
                            />
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Note méthodologique */}
          <div className="card border-ink-700/50 bg-ink-900/40 p-4">
            <p className="text-[11px] leading-relaxed text-slate-500">{data.note}</p>
            <p className="mt-2 text-[10px] text-slate-600">
              ⚠️ Projection indicative : les probabilités sont figées (Elo actuel) et le départage
              en cas d'égalité de points est alphabétique. Championnat : {leagueName}.
            </p>
          </div>
        </>
      )}
    </div>
  );
}

export default function SimulationPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col items-center justify-center py-20">
          <div className="flex h-8 w-8 rounded-full border-4 border-ink-700 border-t-accent animate-spin" />
          <p className="mt-4 text-sm text-slate-400">Chargement de la simulation…</p>
        </div>
      }
    >
      <SimulationContent />
    </Suspense>
  );
}