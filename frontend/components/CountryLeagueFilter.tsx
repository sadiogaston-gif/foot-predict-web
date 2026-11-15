"use client";

import { COUNTRIES, COUNTRY_FLAGS, leaguesForCountry, LEAGUES } from "@/lib/leagues";
import LeagueBadge from "@/components/LeagueBadge";

interface Props {
  country: string;
  league: string;
  onCountryChange: (country: string) => void;
  onLeagueChange: (league: string) => void;
  /** Autorise l'option « Toutes les ligues » (utile pour la liste des matchs). */
  allowAllLeagues?: boolean;
}

const chipClass = (active: boolean) =>
  `link-focus rounded-lg px-3 py-1.5 text-[12px] font-medium transition ${
    active
      ? "bg-ink-700 text-fg shadow-sm"
      : "text-slate-400 hover:bg-ink-800 hover:text-slate-200"
  }`;

export default function CountryLeagueFilter({
  country,
  league,
  onCountryChange,
  onLeagueChange,
  allowAllLeagues = true,
}: Props) {
  const leagues = leaguesForCountry(country);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-ink-700/70 bg-ink-900/60 p-1.5">
        <span className="px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Pays
        </span>
        <button
          type="button"
          onClick={() => onCountryChange("ALL")}
          aria-pressed={country === "ALL"}
          className={chipClass(country === "ALL")}
        >
          Tous
        </button>
        {COUNTRIES.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => onCountryChange(name)}
            aria-pressed={country === name}
            className={chipClass(country === name)}
          >
            {COUNTRY_FLAGS[name] ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={COUNTRY_FLAGS[name]}
                alt=""
                className="mr-1.5 inline-block h-3 w-4 rounded-[2px] object-cover align-[-1px]"
              />
            ) : null}
            {name}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-ink-700/70 bg-ink-900/60 p-1.5">
        <span className="px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Championnat
        </span>
        {allowAllLeagues ? (
          <button
            type="button"
            onClick={() => onLeagueChange("ALL")}
            aria-pressed={league === "ALL"}
            className={chipClass(league === "ALL")}
          >
            Tous
          </button>
        ) : null}
        {leagues.map((item) => (
          <button
            key={item.code}
            type="button"
            onClick={() => onLeagueChange(item.code)}
            aria-pressed={league === item.code}
            className={chipClass(league === item.code)}
          >
            <span className="mr-1.5 inline-flex items-center align-[-2px]">
              <LeagueBadge code={item.code} size={16} />
            </span>
            {item.name}
          </button>
        ))}
        {leagues.length === 0 ? (
          <span className="px-2 text-[12px] text-slate-500">Aucun championnat.</span>
        ) : null}
      </div>
    </div>
  );
}

export { LEAGUES };
