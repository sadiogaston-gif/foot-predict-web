"use client";

import { COUNTRIES, COUNTRY_FLAGS, leaguesForCountry, LEAGUES } from "@/lib/leagues";
import FilterDropdown, { type DropdownOption } from "@/components/FilterDropdown";
import LeagueBadge from "@/components/LeagueBadge";

interface Props {
  country: string;
  league: string;
  onCountryChange: (country: string) => void;
  onLeagueChange: (league: string) => void;
  /** Autorise l'option « Toutes les ligues » (utile pour la liste des matchs). */
  allowAllLeagues?: boolean;
}

function Flag({ name }: { name: string }) {
  if (!COUNTRY_FLAGS[name]) return null;
  return (
    <img
      src={COUNTRY_FLAGS[name]}
      alt=""
      className="h-3.5 w-5 rounded-[2px] object-cover"
    />
  );
}

export default function CountryLeagueFilter({
  country,
  league,
  onCountryChange,
  onLeagueChange,
  allowAllLeagues = true,
}: Props) {
  const leagues = leaguesForCountry(country);

  const countryOptions: DropdownOption[] = [
    { value: "ALL", label: "Tous les pays", icon: <span className="text-[13px]">🌐</span> },
    ...COUNTRIES.map((name) => ({
      value: name,
      label: name,
      icon: <Flag name={name} />,
    })),
  ];

  const leagueOptions: DropdownOption[] = [
    ...(allowAllLeagues
      ? [{ value: "ALL", label: "Tous les championnats", icon: <span className="text-[13px]">🏆</span> }]
      : []),
    ...leagues.map((item) => ({
      value: item.code,
      label: item.name,
      icon: <LeagueBadge code={item.code} size={16} />,
    })),
  ];

  return (
    <section className="flex flex-col gap-2.5 px-4 sm:flex-row sm:items-center md:px-6">
      <FilterDropdown
        label="Pays"
        value={country}
        options={countryOptions}
        onChange={onCountryChange}
        className="sm:w-56"
      />
      <FilterDropdown
        label="Championnat"
        value={league}
        options={leagueOptions}
        onChange={onLeagueChange}
        className="sm:w-64"
      />
    </section>
  );
}

export { LEAGUES };