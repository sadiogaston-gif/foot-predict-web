import type {
  ExternalContext,
  ExternalInjury,
  ExternalLastRatings,
  ExternalLineupTeam,
  ExternalRatingPlayer,
  ExternalSquadPlayer,
  ExternalStandingRow,
} from "@/lib/types";

const POSITION_LABEL: Record<string, string> = {
  Goalkeeper: "Gardiens",
  Defender: "Défenseurs",
  Midfielder: "Milieux",
  Attacker: "Attaquants",
};

const POSITION_ORDER = ["Goalkeeper", "Defender", "Midfielder", "Attacker"];

function groupSquad(players: ExternalSquadPlayer[] | null | undefined) {
  const groups: Record<string, ExternalSquadPlayer[]> = {};
  for (const player of players ?? []) {
    const key = player.position && POSITION_LABEL[player.position] ? player.position : "Autres";
    (groups[key] ??= []).push(player);
  }
  return groups;
}

function StandingCard({ label, row }: { label: string; row: ExternalStandingRow | null }) {
  if (!row) return null;
  return (
    <div className="rounded-xl border border-ink-700/70 bg-ink-900/50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {label} · classement
      </p>
      <div className="mt-1 flex items-baseline justify-between gap-2">
        <span className="text-[13px] text-slate-200">
          {row.position}
          <sup>e</sup> · {row.points} pts
        </span>
        <span className="font-mono text-[10px] text-slate-500">
          {row.played} m · {row.won}V {row.draw}N {row.lost}D
        </span>
      </div>
      {row.form ? (
        <p className="mt-1 font-mono text-[10px] tracking-[0.2em] text-slate-400">{row.form}</p>
      ) : null}
    </div>
  );
}

function InjuryColumn({
  team,
  injuries,
  available,
  note,
}: {
  team: string;
  injuries: ExternalInjury[] | null | undefined;
  available?: boolean;
  note?: string | null;
}) {
  const list = injuries ?? [];
  return (
    <div className="rounded-xl border border-ink-700/70 bg-ink-900/50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {team} · absences
      </p>
      {!available ? (
        <p className="mt-1.5 text-[12px] leading-relaxed text-slate-500">
          {note ?? "Données d'absences indisponibles."}
        </p>
      ) : list.length === 0 ? (
        <p className="mt-1.5 text-[12px] text-slate-500">Aucune absence signalée.</p>
      ) : (
        <ul className="mt-1.5 space-y-1.5">
          {list.map((injury, index) => (
            <li key={`${injury.player}-${index}`} className="flex items-start justify-between gap-2 text-[12px]">
              <span className="text-slate-200">{injury.player}</span>
              <span className="text-right text-[11px] text-slate-500">
                {injury.reason || injury.type || "Indisponible"}
                {injury.fixture_date ? ` · ${injury.fixture_date}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SquadDetails({
  team,
  players,
  note,
}: {
  team: string;
  players: ExternalSquadPlayer[] | null | undefined;
  note?: string | null;
}) {
  const groups = groupSquad(players);
  const orderedKeys = [
    ...POSITION_ORDER.filter((key) => groups[key]?.length),
    ...Object.keys(groups).filter((key) => key === "Autres"),
  ];
  const total = (players ?? []).length;

  return (
    <details className="rounded-xl border border-ink-700/70 bg-ink-900/50 p-3">
      <summary className="cursor-pointer select-none text-[12px] font-medium text-slate-200">
        {team} · effectif{total ? ` (${total})` : ""}
      </summary>
      {total === 0 ? (
        <p className="mt-2 text-[12px] leading-relaxed text-slate-500">
          {note ?? "Effectif non disponible."}
        </p>
      ) : (
        <div className="mt-3 space-y-3">
          {orderedKeys.map((key) => (
            <div key={key}>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {POSITION_LABEL[key] ?? "Autres"}
              </p>
              <ul className="mt-1 grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2">
                {groups[key].map((player) => (
                  <li key={player.id ?? player.name} className="flex items-baseline gap-2 text-[12px]">
                    <span className="tnum w-5 shrink-0 text-right font-mono text-[10px] text-slate-500">
                      {player.number ?? "—"}
                    </span>
                    <span className="truncate text-slate-200">{player.name}</span>
                    {player.age ? (
                      <span className="ml-auto shrink-0 font-mono text-[10px] text-slate-600">
                        {player.age} ans
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </details>
  );
}

function Lineups({ teams }: { teams: ExternalLineupTeam[] }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        Compositions
      </p>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        {teams.map((team) => (
          <div key={team.team} className="rounded-xl border border-ink-700/70 bg-ink-900/50 p-3">
            <p className="text-[12px] font-medium text-slate-200">
              {team.team}
              {team.formation ? (
                <span className="ml-2 rounded border border-ink-600 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                  {team.formation}
                </span>
              ) : null}
            </p>
            {team.coach ? (
              <p className="mt-0.5 text-[10px] text-slate-500">Entraîneur : {team.coach}</p>
            ) : null}
            <ul className="mt-2 grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2">
              {team.startXI.map((player, index) => (
                <li key={`${player.name}-${index}`} className="flex items-baseline gap-2 text-[12px]">
                  <span className="tnum w-5 shrink-0 text-right font-mono text-[10px] text-slate-500">
                    {player.number ?? "—"}
                  </span>
                  <span className="truncate text-slate-200">{player.name}</span>
                  {player.position ? (
                    <span className="ml-auto shrink-0 font-mono text-[10px] text-slate-600">
                      {player.position}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function ratingClass(rating: number) {
  if (rating >= 7.5) return "border-accent/40 bg-accent/10 text-accent";
  if (rating >= 7) return "border-info/40 bg-info/10 text-info";
  return "border-ink-600 bg-ink-800 text-slate-300";
}

function Ratings({
  teams,
  title = "Notes des joueurs",
}: {
  teams: { team: string; players: ExternalRatingPlayer[] }[];
  title?: string;
}) {
  const hasRatings = teams.some((team) => team.players.length > 0);
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {title} {hasRatings ? "" : "(indisponibles)"}
      </p>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        {teams.map((team) => (
          <div key={team.team} className="rounded-xl border border-ink-700/70 bg-ink-900/50 p-3">
            <p className="text-[12px] font-medium text-slate-200">{team.team}</p>
            {team.players.length === 0 ? (
              <p className="mt-1.5 text-[12px] text-slate-500">Pas encore de notes.</p>
            ) : (
              <ul className="mt-1.5 space-y-1">
                {team.players.map((player) => (
                  <li key={player.name} className="flex items-center justify-between gap-2 text-[12px]">
                    <span className="truncate text-slate-200">{player.name}</span>
                    <span className="flex shrink-0 items-center gap-1.5">
                      {player.minutes ? (
                        <span className="font-mono text-[10px] text-slate-600">{player.minutes}&apos;</span>
                      ) : null}
                      <span
                        className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${ratingClass(player.rating)}`}
                      >
                        {player.rating.toFixed(1)}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ExternalContextSection({
  external,
  homeTeam,
  awayTeam,
}: {
  external: ExternalContext;
  homeTeam: string;
  awayTeam: string;
}) {
  if (!external?.available) {
    return (
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-fg">Effectifs, blessures &amp; compositions</h2>
        <p className="mt-2 text-[12px] leading-relaxed text-slate-500">
          {external?.reason ?? "Source externe non configurée."}
        </p>
        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-600">
          Pour activer ces données : créer une clé gratuite sur api-football.com (100 requêtes/jour)
          puis définir <span className="font-mono text-slate-400">API_FOOTBALL_KEY</span> dans le
          fichier <span className="font-mono text-slate-400">.env</span>. Ces informations
          n&apos;entrent pas dans le calcul des probabilités.
        </p>
      </section>
    );
  }

  const injuries = external.injuries;
  const squads = external.squads;
  const lineups = external.lineups?.teams ?? [];
  const ratings = external.ratings?.teams ?? [];
  const notes = external.notes ?? {};
  const standings = external.standings;
  const lastRatings = [external.last_ratings?.home, external.last_ratings?.away].filter(
    (entry): entry is ExternalLastRatings => Boolean(entry),
  );

  return (
    <section className="card space-y-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-fg">
          Effectifs, blessures &amp; compositions
        </h2>
        <span className="chip border-ink-600 text-[10px]">
          Football-Data.org · API-Football · Highlightly
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <InjuryColumn
          team={homeTeam}
          injuries={injuries?.home}
          available={external.injuries_available}
          note={notes.injuries}
        />
        <InjuryColumn
          team={awayTeam}
          injuries={injuries?.away}
          available={external.injuries_available}
          note={notes.injuries}
        />
      </div>

      {standings && (standings.home || standings.away) ? (
        <div className="grid gap-3 md:grid-cols-2">
          <StandingCard label={homeTeam} row={standings.home} />
          <StandingCard label={awayTeam} row={standings.away} />
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <SquadDetails team={homeTeam} players={squads?.home} note={notes.squads} />
        <SquadDetails team={awayTeam} players={squads?.away} note={notes.squads} />
      </div>

      {lineups.length > 0 ? (
        <Lineups teams={lineups} />
      ) : (
        <p className="text-[11px] leading-relaxed text-slate-600">
          {notes.lineups ?? "Compositions non publiées."}
        </p>
      )}

      {ratings.length > 0 ? (
        <Ratings teams={ratings} />
      ) : lastRatings.length > 0 ? (
        <Ratings
          teams={lastRatings.map((entry) => ({
            team: entry.date ? `${entry.team} · ${entry.date}` : entry.team,
            players: entry.players,
          }))}
          title="Notes du dernier match"
        />
      ) : (
        <p className="text-[11px] leading-relaxed text-slate-600">
          {notes.ratings ?? "Notes des joueurs indisponibles."}
        </p>
      )}

      <p className="text-[10px] leading-relaxed text-slate-600">
        Données contextuelles fournies à titre informatif : elles ne sont pas historisées et
        n&apos;entrent pas dans le modèle de probabilités.
      </p>
    </section>
  );
}
