"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import TeamBadge from "@/components/TeamBadge";
import LeagueBadge from "@/components/LeagueBadge";
import { apiGet } from "@/lib/api";
import { formatDate, pct } from "@/lib/format";
import type { TeamFormContext } from "@/lib/types";

interface TeamRow {
  name: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goals_for: number;
  goals_against: number;
  avg_goals_for: number;
  avg_goals_against: number;
  clean_sheets: number;
  clean_sheet_rate: number;
  failed_to_score: number;
  btts_count: number;
  btts_rate: number;
  over_2_5_count: number;
  over_2_5_rate: number;
  streak: { type: "W" | "D" | "L" | null; length: number; label: string };
  rest_days: number | null;
  matches_last_14_days: number;
  elo_trend: { current: number; delta_5: number } | null;
}

interface TeamRowRow extends TeamRow {
  position: number;
}

export default function LeagueTeamsPage() {
  const { league } = useParams<{ league: string }>();
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"points" | "goals" | "name">("points");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const load = useCallback(async () => {
    if (!league) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiGet<{ teams: TeamRow[] }>(
        `/api/teams/${league}`
      );
      setTeams(response.teams || []);
    } catch (err: any) {
      setError(err?.message ?? "Échec du chargement des équipes");
    } finally {
      setLoading(false);
    }
  }, [league]);

  useEffect(() => {
    load();
  }, [load, league]);

  const sorted = [...teams].sort((a, b) => {
    let cmp = 0;
    if (sortBy === "points") cmp = a.points - b.points;
    else if (sortBy === "goals") cmp = a.goals_for - a.goals_against - (b.goals_for - b.goals_against);
    else cmp = a.name.localeCompare(b.name);
    return sortDir === "asc" ? cmp : -cmp;
  });

  const formatted = sorted.map((team, index) => ({
    ...team,
    position: index + 1,
  }));

  const statusColor = (type: string | null) => {
    switch (type) {
      case "W": return "text-emerald-400";
      case "D": return "text-amber-400";
      case "L": return "text-danger";
      default: return "text-slate-500";
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="flex h-8 w-8 rounded-full border-4 border-ink-700 border-t-accent animate-spin" />
        <p className="mt-4 text-sm text-slate-400">Chargement des équipes...</p>
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

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col lg:flex-row items-start justify-between gap-4 px-4">
        <div>
          <Link href="/" className="link-focus text-[11px] font-medium text-accent/80 hover:text-accent">
            ← Retour aux championnats
          </Link>
          <h1 className="text-[24px] font-semibold tracking-tight text-fg sm:text-3xl mt-2">
            {league}
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            {teams.length} équipes - Saison 2026/2027
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="rounded-lg border border-ink-700/70 bg-ink-800/60 px-3 py-2 text-[12px] text-slate-300 focus:outline-none focus:ring-2 focus:ring-accent/50"
          >
            <option value="points">Trier par points</option>
            <option value="goals">Trier par différence de buts</option>
            <option value="name">Trier par nom</option>
          </select>
          <button
            onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
            className="link-focus px-3 py-2 text-[12px] text-slate-400 hover:text-fg"
          >
            {sortDir === "asc" ? "▲" : "▼"}
          </button>
        </div>
      </div>

      <div className="card p-4 overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead className="sticky top-0 bg-ink-950/80 backdrop-blur-sm">
            <tr className="border-b border-ink-700/60">
              <th className="text-left pb-2 text-slate-500">#</th>
              <th className="text-left pb-2 text-slate-500">Équipe</th>
              <th className="text-right pb-2 text-slate-500">J</th>
              <th className="text-right pb-2 text-slate-500">G</th>
              <th className="text-right pb-2 text-slate-500">N</th>
              <th className="text-right pb-2 text-slate-500">P</th>
              <th className="text-right pb-2 text-slate-500">Pts</th>
              <th className="text-right pb-2 text-slate-500">BM</th>
              <th className="text-right pb-2 text-slate-500">BC</th>
              <th className="text-right pb-2 text-slate-500">Diff</th>
              <th className="text-right pb-2 text-slate-500">Forme</th>
            </tr>
          </thead>
          <tbody>
            {formatted.map((team) => (
              <tr key={team.name} className="border-b border-ink-700/40 hover:bg-ink-800/30">
                <td className="pb-1 text-right font-mono text-slate-400">{team.position}</td>
                <td className="pb-1 flex items-center gap-2">
                  <TeamBadge name={team.name} size={16} />
                  <span className="text-slate-300">{team.name}</span>
                </td>
                <td className="pb-1 text-right font-mono text-slate-300">{team.played}</td>
                <td className="pb-1 text-right font-mono text-emerald-400">{team.wins}</td>
                <td className="pb-1 text-right font-mono text-amber-400">{team.draws}</td>
                <td className="pb-1 text-right font-mono text-danger">{team.losses}</td>
                <td className="pb-1 text-right font-mono text-fg">{team.points}</td>
                <td className="pb-1 text-right font-mono text-slate-300">{team.goals_for}</td>
                <td className="pb-1 text-right font-mono text-slate-300">{team.goals_against}</td>
                <td className="pb-1 text-right font-mono">
                  {team.goals_for - team.goals_against >= 0 ? "+" : ""}
                  {team.goals_for - team.goals_against}
                </td>
                <td className="pb-1 flex gap-1">
                  {team.streak.streak ? (
                    <span className={`tnum font-mono ${statusColor(team.streak.streak)}`}>
                      {team.streak.streak}
                    </span>
                  ) : (
                    <span className="tnum font-mono text-slate-500">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Détails par équipe */}
      <div className="grid gap-4 px-4 sm:grid-cols-2 lg:grid-cols-4">
        {teams.slice(0, 8).map((team) => (
          <div key={team.name} className="card p-4 space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <TeamBadge name={team.name} size={24} />
              <span className="text-sm font-semibold text-fg">{team.name}</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="flex items-center gap-1 text-[10px]">
                <span className="text-slate-500">J:</span>
                <span className="tnum font-mono text-slate-300">{team.played}</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <span className="text-slate-500">Pts:</span>
                <span className="tnum font-mono text-fg">{team.points}</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <span className="text-slate-500">BM:</span>
                <span className="tnum font-mono text-slate-300">{team.goals_for}</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <span className="text-slate-500">BC:</span>
                <span className="tnum font-mono text-slate-300">{team.goals_against}</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <span className="text-slate-500">BTTS:</span>
                <span className="tnum font-mono text-slate-300">{pct(team.btts_rate)}</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <span className="text-slate-500">O2.5:</span>
                <span className="tnum font-mono text-slate-300">{pct(team.over_2_5_rate)}</span>
              </div>
            </div>
            <div className="flex gap-1 mt-2">
              {team.streak.streak && (
                <span
                  className={`tnum font-mono text-[10px] ${statusColor(team.streak.streak)}`}
                >
                  {team.streak.streak} ×{team.streak.length}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
