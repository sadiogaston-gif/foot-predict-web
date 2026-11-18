/**
 * Référentiel des championnats suivis (première et deuxième divisions).
 * Source de vérité côté UI ; l'API expose le même référentiel via /api/leagues.
 *
 * `logo` : emblème officiel fourni par Football-Data.org ou football-logos.cc.
 * Les championnats sans emblème affichent un badge généré.
 */

export interface LeagueOption {
  code: string;
  name: string;
  country: string;
  logo?: string;
}

const CREST = "https://crests.football-data.org";
const FL = "https://assets.football-logos.cc/logos";

export const LEAGUES: LeagueOption[] = [
  { code: "E0", name: "Premier League", country: "Angleterre", logo: `${CREST}/PL.png` },
  { code: "E1", name: "Championship", country: "Angleterre", logo: `${CREST}/ELC.png` },
  { code: "F1", name: "Ligue 1", country: "France", logo: `${CREST}/FL1.png` },
  { code: "F2", name: "Ligue 2", country: "France", logo: `${FL}/france/700x700/ligue-2.aef87665.png` },
  { code: "D1", name: "Bundesliga", country: "Allemagne", logo: `${CREST}/BL1.png` },
  { code: "D2", name: "2. Bundesliga", country: "Allemagne", logo: `${FL}/germany/700x700/2-bundesliga.e2512d8d.png` },
  { code: "I1", name: "Serie A", country: "Italie", logo: `${CREST}/c111.png` },
  { code: "I2", name: "Serie B", country: "Italie", logo: `${FL}/italy/700x700/serie-b.d27003ee.png` },
  { code: "SP1", name: "La Liga", country: "Espagne", logo: `${CREST}/laliga.png` },
  { code: "SP2", name: "Segunda División", country: "Espagne", logo: `${FL}/spain/700x700/la-liga-2.e0084660.png` },
  { code: "P1", name: "Primeira Liga", country: "Portugal", logo: `${CREST}/PPL.png` },
  { code: "P2", name: "Liga Portugal 2", country: "Portugal", logo: `${FL}/portugal/700x700/liga-portugal-2.1ef19ad5.png` },
  { code: "N1", name: "Eredivisie", country: "Pays-Bas", logo: `${FL}/netherlands/700x700/eredivisie.846bf0f7.png` },
  { code: "B1", name: "Jupiler Pro League", country: "Belgique", logo: `${FL}/belgium/256x256/jupiler-pro-league.88f9b202.png` },
  { code: "T1", name: "Süper Lig", country: "Turquie", logo: `${FL}/turkey/700x700/super-lig.b375bfcd.png` },
  { code: "SC0", name: "Scottish Premiership", country: "Écosse", logo: `${FL}/scotland/700x700/scottish-premiership.b3d4bdfb.png` },
  { code: "G1", name: "Super League", country: "Grèce" },
  { code: "T2", name: "1. Lig", country: "Turquie" },
];

export const COUNTRIES: string[] = Array.from(
  new Set(LEAGUES.map((league) => league.country)),
);

/** Drapeaux (flagcdn, libres d'usage) pour chaque pays couvert. */
export const COUNTRY_FLAGS: Record<string, string> = {
  Angleterre: "https://flagcdn.com/w40/gb-eng.png",
  France: "https://flagcdn.com/w40/fr.png",
  Allemagne: "https://flagcdn.com/w40/de.png",
  Italie: "https://flagcdn.com/w40/it.png",
  Espagne: "https://flagcdn.com/w40/es.png",
  Portugal: "https://flagcdn.com/w40/pt.png",
  "Pays-Bas": "https://flagcdn.com/w40/nl.png",
  Belgique: "https://flagcdn.com/w40/be.png",
  Turquie: "https://flagcdn.com/w40/tr.png",
  Écosse: "https://flagcdn.com/w40/gb-sct.png",
  Grèce: "https://flagcdn.com/w40/gr.png",
};

export function leaguesForCountry(country: string): LeagueOption[] {
  if (country === "ALL") return LEAGUES;
  return LEAGUES.filter((league) => league.country === country);
}

export function leagueByCode(code: string): LeagueOption | undefined {
  return LEAGUES.find((league) => league.code === code);
}
