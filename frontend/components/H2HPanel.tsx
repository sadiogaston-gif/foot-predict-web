"use client";

import type { MatchDetail } from "@/lib/types";

interface H2HMatch {
  date: string;
  home: string;
  away: string;
  home_goals: number;
  away_goals: number;
  status: string;
}

/** Bandeau des dernières confrontations directes (H2H). */
export default function H2HPanel({ match }: { match: MatchDetail }) {
  const h2h = match.external?.h2h ?? [];
  if (h2h.length === 0) return null;

  const home = match.home_team;
  const away = match.away_team;

  // Statistiques sur les confrontations disponibles, du point de vue de l'équipe domicile.
  let homeWins = 0;
  let draws = 0;
  let awayWins = 0;
  for (const game of h2h) {
    const homeIsHost = game.home === home;
    const myGoals = homeIsHost ? game.home_goals : game.away_goals;
    const oppGoals = homeIsHost ? game.away_goals : game.home_goals;
    if (myGoals > oppGoals) homeWins += 1;
    else if (myGoals === oppGoals) draws += 1;
    else awayWins += 1;
  }

  return (
    <div className="card p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-fg">Dernières confrontations</h2>
        <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
          H2H · {h2h.length} matchs
        </span>
      </div>

      {/* Bilan agrégé du point de vue de l'équipe domicile */}
      <div className="mb-4 grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-accent/20 bg-accent/5 px-2 py-1.5 text-center">
          <p className="tnum font-mono text-base font-semibold text-accent">{homeWins}</p>
          <p className="text-[9px] uppercase tracking-wide text-slate-500">Victoires {home.split(" ").pop()}</p>
        </div>
        <div className="rounded-lg border border-ink-700/60 bg-ink-900/40 px-2 py-1.5 text-center">
          <p className="tnum font-mono text-base font-semibold text-slate-300">{draws}</p>
          <p className="text-[9px] uppercase tracking-wide text-slate-500">Nuls</p>
        </div>
        <div className="rounded-lg border border-info/20 bg-info/5 px-2 py-1.5 text-center">
          <p className="tnum font-mono text-base font-semibold text-info">{awayWins}</p>
          <p className="text-[9px] uppercase tracking-wide text-slate-500">Victoires {away.split(" ").pop()}</p>
        </div>
      </div>

      {/* Liste des matchs */}
      <ul className="space-y-1.5">
        {h2h.map((game, index) => {
          const homeIsHost = game.home === home;
          const hostName = game.home;
          const guestName = game.away;
          const hostGoals = game.home_goals;
          const guestGoals = game.away_goals;
          return (
            <li
              key={`${game.date}-${index}`}
              className="flex items-center justify-between gap-3 rounded-md border border-ink-700/40 bg-ink-900/30 px-3 py-1.5 text-[11px]"
            >
              <span className="min-w-0 flex-1 truncate text-right text-slate-400">
                {hostIsHomeDisplay(hostName, home, away)}
              </span>
              <span className="tnum shrink-0 font-mono font-semibold text-fg">
                {hostGoals} - {guestGoals}
              </span>
              <span className="min-w-0 flex-1 truncate text-slate-400">
                {hostIsHomeDisplay(guestName, home, away)}
              </span>
              <span className="shrink-0 font-mono text-[9px] text-slate-600">{game.date}</span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[9px] text-slate-600">
        Confrontations passées · source API-Football
      </p>
    </div>
  );
}

/** Retourne un libellé court pour l'équipe (nom complet sinon). */
function hostIsHomeDisplay(name: string, home: string, away: string): string {
  if (name === home) return home.split(" ").pop() || home;
  if (name === away) return away.split(" ").pop() || away;
  return name;
}