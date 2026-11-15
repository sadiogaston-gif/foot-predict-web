"""
backend/team_mapping.py - Correspondance des noms d'équipes The Odds API -> Football-Data.co.uk

The Odds API renvoie les noms « officiels » des clubs (ex. « Manchester United »,
« Paris Saint Germain », « Borussia Mönchengladbach »), tandis que nos CSV
historiques Football-Data.co.uk utilisent des noms abrégés (ex. « Man United »,
« Paris SG », « M'gladbach »).

Ce module fournit :
  1. TEAM_ALIASES : dictionnaire complet, par championnat, des variantes de noms
     rencontrées côté The Odds API vers le nom EXACT utilisé dans les CSV.
  2. normalize_name() : normalisation (minuscules, accents retirés, ponctuation
     neutralisée) pour comparer les noms sans être sensible à l'orthographe.
  3. map_team_name() : résolution en trois temps — correspondance exacte,
     correspondance floue (difflib.get_close_matches), puis repli par sous-chaîne.
     Si rien ne correspond, le nom d'origine est renvoyé avec la méthode
     « unmapped » : aucune exception n'est levée, le pipeline ne plante jamais.
  4. historical_teams() : équipes réellement présentes dans data/raw/, utilisées
     comme vivier de secours (utile quand un club promu n'est pas encore dans le
     dictionnaire statique).

Championnats couverts (codes Football-Data) :
    E0 = Premier League     F1 = Ligue 1     D1 = Bundesliga
    I1 = Serie A            SP1 = La Liga    P1 = Primeira Liga
    N1 = Eredivisie
"""

from __future__ import annotations

import difflib
import os
import unicodedata
from functools import lru_cache

# ---------------------------------------------------------------------------
# Dictionnaire principal : code championnat -> {nom The Odds API: nom Football-Data}
#
# Les clés peuvent contenir des accents : la normalisation s'en charge.
# Plusieurs variantes pointent vers le même nom cible (les bookmakers diffèrent).
# ---------------------------------------------------------------------------
TEAM_ALIASES: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ E0
    "E0": {
        "Arsenal": "Arsenal",
        "Aston Villa": "Aston Villa",
        "Bournemouth": "Bournemouth",
        "AFC Bournemouth": "Bournemouth",
        "Brentford": "Brentford",
        "Brighton": "Brighton",
        "Brighton and Hove Albion": "Brighton",
        "Brighton & Hove Albion": "Brighton",
        "Burnley": "Burnley",
        "Chelsea": "Chelsea",
        "Coventry": "Coventry",
        "Coventry City": "Coventry",
        "Crystal Palace": "Crystal Palace",
        "Everton": "Everton",
        "Fulham": "Fulham",
        "Hull": "Hull",
        "Hull City": "Hull",
        "Ipswich": "Ipswich",
        "Ipswich Town": "Ipswich",
        "Leeds": "Leeds",
        "Leeds United": "Leeds",
        "Leicester": "Leicester",
        "Leicester City": "Leicester",
        "Liverpool": "Liverpool",
        "Manchester City": "Man City",
        "Man City": "Man City",
        "Manchester United": "Man United",
        "Man United": "Man United",
        "Man Utd": "Man United",
        "Newcastle": "Newcastle",
        "Newcastle United": "Newcastle",
        "Nottingham Forest": "Nott'm Forest",
        "Nottm Forest": "Nott'm Forest",
        "Nott'm Forest": "Nott'm Forest",
        "Southampton": "Southampton",
        "Sunderland": "Sunderland",
        "Tottenham": "Tottenham",
        "Tottenham Hotspur": "Tottenham",
        "West Ham": "West Ham",
        "West Ham United": "West Ham",
        "Wolves": "Wolves",
        "Wolverhampton": "Wolves",
        "Wolverhampton Wanderers": "Wolves",
    },
    # ------------------------------------------------------------------ F1
    "F1": {
        "Angers": "Angers",
        "Angers SCO": "Angers",
        "Auxerre": "Auxerre",
        "AJ Auxerre": "Auxerre",
        "Brest": "Brest",
        "Stade Brestois": "Brest",
        "Stade Brestois 29": "Brest",
        "Le Havre": "Le Havre",
        "Le Havre AC": "Le Havre",
        "Havre AC": "Le Havre",
        "Le Mans": "Le Mans",
        "Le Mans FC": "Le Mans",
        "Lens": "Lens",
        "RC Lens": "Lens",
        "Racing Club de Lens": "Lens",
        "Racing Club Lens": "Lens",
        "Lille": "Lille",
        "LOSC Lille": "Lille",
        "Lille OSC": "Lille",
        "Lorient": "Lorient",
        "FC Lorient": "Lorient",
        "Lyon": "Lyon",
        "Olympique Lyonnais": "Lyon",
        "Olympique Lyon": "Lyon",
        "Marseille": "Marseille",
        "Olympique de Marseille": "Marseille",
        "Olympique Marseille": "Marseille",
        "Metz": "Metz",
        "FC Metz": "Metz",
        "Monaco": "Monaco",
        "AS Monaco": "Monaco",
        "Montpellier": "Montpellier",
        "Montpellier HSC": "Montpellier",
        "Nantes": "Nantes",
        "FC Nantes": "Nantes",
        "Nice": "Nice",
        "OGC Nice": "Nice",
        "Paris FC": "Paris FC",
        "Paris FC 2000": "Paris FC",
        "Paris Saint-Germain": "Paris SG",
        "Paris Saint Germain": "Paris SG",
        "Paris SG": "Paris SG",
        "PSG": "Paris SG",
        "Reims": "Reims",
        "Stade de Reims": "Reims",
        "Stade Reims": "Reims",
        "Rennes": "Rennes",
        "Stade Rennais": "Rennes",
        "Stade Rennais FC": "Rennes",
        "St Etienne": "St Etienne",
        "Saint-Etienne": "St Etienne",
        "Saint Etienne": "St Etienne",
        "AS Saint-Etienne": "St Etienne",
        "AS Saint Etienne": "St Etienne",
        "Strasbourg": "Strasbourg",
        "RC Strasbourg": "Strasbourg",
        "RC Strasbourg Alsace": "Strasbourg",
        "Toulouse": "Toulouse",
        "Toulouse FC": "Toulouse",
        "Troyes": "Troyes",
        "ES Troyes AC": "Troyes",
        "Troyes AC": "Troyes",
    },
    # ------------------------------------------------------------------ D1
    "D1": {
        "Augsburg": "Augsburg",
        "FC Augsburg": "Augsburg",
        "Bayern Munich": "Bayern Munich",
        "Bayern München": "Bayern Munich",
        "Bayern Muenchen": "Bayern Munich",
        "FC Bayern Munich": "Bayern Munich",
        "FC Bayern München": "Bayern Munich",
        "Bochum": "Bochum",
        "VfL Bochum": "Bochum",
        "VfL Bochum 1848": "Bochum",
        "Borussia Dortmund": "Dortmund",
        "Dortmund": "Dortmund",
        "BVB": "Dortmund",
        "Eintracht Frankfurt": "Ein Frankfurt",
        "Ein Frankfurt": "Ein Frankfurt",
        "Frankfurt": "Ein Frankfurt",
        "Elversberg": "Elversberg",
        "SV Elversberg": "Elversberg",
        "FC Koln": "FC Koln",
        "1. FC Köln": "FC Koln",
        "1. FC Koln": "FC Koln",
        "FC Cologne": "FC Koln",
        "Koln": "FC Koln",
        "Cologne": "FC Koln",
        "Freiburg": "Freiburg",
        "SC Freiburg": "Freiburg",
        "Hamburg": "Hamburg",
        "Hamburger SV": "Hamburg",
        "HSV": "Hamburg",
        "Heidenheim": "Heidenheim",
        "1. FC Heidenheim": "Heidenheim",
        "FC Heidenheim": "Heidenheim",
        "Hoffenheim": "Hoffenheim",
        "TSG Hoffenheim": "Hoffenheim",
        "TSG 1899 Hoffenheim": "Hoffenheim",
        "Holstein Kiel": "Holstein Kiel",
        "Kiel": "Holstein Kiel",
        "Leverkusen": "Leverkusen",
        "Bayer Leverkusen": "Leverkusen",
        "Bayer 04 Leverkusen": "Leverkusen",
        "M'gladbach": "M'gladbach",
        "Borussia Mönchengladbach": "M'gladbach",
        "Borussia Monchengladbach": "M'gladbach",
        "Borussia Moenchengladbach": "M'gladbach",
        "Monchengladbach": "M'gladbach",
        "Moenchengladbach": "M'gladbach",
        "Gladbach": "M'gladbach",
        "Mainz": "Mainz",
        "Mainz 05": "Mainz",
        "1. FSV Mainz 05": "Mainz",
        "Paderborn": "Paderborn",
        "SC Paderborn": "Paderborn",
        "SC Paderborn 07": "Paderborn",
        "RB Leipzig": "RB Leipzig",
        "Leipzig": "RB Leipzig",
        "Schalke 04": "Schalke 04",
        "Schalke": "Schalke 04",
        "FC Schalke 04": "Schalke 04",
        "St Pauli": "St Pauli",
        "FC St. Pauli": "St Pauli",
        "FC St Pauli": "St Pauli",
        "St. Pauli": "St Pauli",
        "Sankt Pauli": "St Pauli",
        "Stuttgart": "Stuttgart",
        "VfB Stuttgart": "Stuttgart",
        "Union Berlin": "Union Berlin",
        "1. FC Union Berlin": "Union Berlin",
        "Werder Bremen": "Werder Bremen",
        "Bremen": "Werder Bremen",
        "Wolfsburg": "Wolfsburg",
        "VfL Wolfsburg": "Wolfsburg",
    },
    # ------------------------------------------------------------------ I1
    "I1": {
        "Atalanta": "Atalanta",
        "Atalanta BC": "Atalanta",
        "Bologna": "Bologna",
        "Bologna FC": "Bologna",
        "Cagliari": "Cagliari",
        "Cagliari Calcio": "Cagliari",
        "Como": "Como",
        "Como 1907": "Como",
        "Cremonese": "Cremonese",
        "US Cremonese": "Cremonese",
        "Empoli": "Empoli",
        "Empoli FC": "Empoli",
        "Fiorentina": "Fiorentina",
        "ACF Fiorentina": "Fiorentina",
        "Frosinone": "Frosinone",
        "Frosinone Calcio": "Frosinone",
        "Genoa": "Genoa",
        "Genoa CFC": "Genoa",
        "Inter": "Inter",
        "Inter Milan": "Inter",
        "Internazionale": "Inter",
        "Juventus": "Juventus",
        "Juventus FC": "Juventus",
        "Lazio": "Lazio",
        "SS Lazio": "Lazio",
        "Lecce": "Lecce",
        "US Lecce": "Lecce",
        "Milan": "Milan",
        "AC Milan": "Milan",
        "Monza": "Monza",
        "AC Monza": "Monza",
        "Napoli": "Napoli",
        "SSC Napoli": "Napoli",
        "Parma": "Parma",
        "Parma Calcio": "Parma",
        "Pisa": "Pisa",
        "AC Pisa": "Pisa",
        "Roma": "Roma",
        "AS Roma": "Roma",
        "Sassuolo": "Sassuolo",
        "US Sassuolo": "Sassuolo",
        "Torino": "Torino",
        "Torino FC": "Torino",
        "Udinese": "Udinese",
        "Udinese Calcio": "Udinese",
        "Venezia": "Venezia",
        "Venezia FC": "Venezia",
        "Verona": "Verona",
        "Hellas Verona": "Verona",
        "Hellas Verona FC": "Verona",
    },
    # ------------------------------------------------------------------ SP1
    "SP1": {
        "Alaves": "Alaves",
        "Deportivo Alaves": "Alaves",
        "Athletic Bilbao": "Ath Bilbao",
        "Athletic Club": "Ath Bilbao",
        "Ath Bilbao": "Ath Bilbao",
        "Atletico Madrid": "Ath Madrid",
        "Atlético Madrid": "Ath Madrid",
        "Atletico de Madrid": "Ath Madrid",
        "Ath Madrid": "Ath Madrid",
        "Barcelona": "Barcelona",
        "FC Barcelona": "Barcelona",
        "Barca": "Barcelona",
        "Betis": "Betis",
        "Real Betis": "Betis",
        "Celta": "Celta",
        "Celta Vigo": "Celta",
        "RC Celta": "Celta",
        "Elche": "Elche",
        "Elche CF": "Elche",
        "Espanol": "Espanol",
        "Espanyol": "Espanol",
        "RCD Espanyol": "Espanol",
        "Getafe": "Getafe",
        "Getafe CF": "Getafe",
        "Girona": "Girona",
        "Girona FC": "Girona",
        "La Coruna": "La Coruna",
        "Deportivo La Coruna": "La Coruna",
        "Deportivo La Coruña": "La Coruna",
        "Deportivo": "La Coruna",
        "Las Palmas": "Las Palmas",
        "UD Las Palmas": "Las Palmas",
        "Leganes": "Leganes",
        "CD Leganes": "Leganes",
        "Levante": "Levante",
        "Levante UD": "Levante",
        "Malaga": "Malaga",
        "Malaga CF": "Malaga",
        "Mallorca": "Mallorca",
        "RCD Mallorca": "Mallorca",
        "Osasuna": "Osasuna",
        "CA Osasuna": "Osasuna",
        "Oviedo": "Oviedo",
        "Real Oviedo": "Oviedo",
        "Real Madrid": "Real Madrid",
        "Santander": "Santander",
        "Racing Santander": "Santander",
        "Racing de Santander": "Santander",
        "Sevilla": "Sevilla",
        "Sevilla FC": "Sevilla",
        "Sociedad": "Sociedad",
        "Real Sociedad": "Sociedad",
        "Valencia": "Valencia",
        "Valencia CF": "Valencia",
        "Valladolid": "Valladolid",
        "Real Valladolid": "Valladolid",
        "Vallecano": "Vallecano",
        "Rayo Vallecano": "Vallecano",
        "Villarreal": "Villarreal",
        "Villarreal CF": "Villarreal",
    },
    # ------------------------------------------------------------------ P1
    "P1": {
        "Academico Viseu": "Academico Viseu",
        "Académico de Viseu": "Academico Viseu",
        "Académico de Viseu FC": "Academico Viseu",
        "Alverca": "Alverca",
        "FC Alverca": "Alverca",
        "Arouca": "Arouca",
        "FC Arouca": "Arouca",
        "AVS": "AVS",
        "AVS Futebol SAD": "AVS",
        "Benfica": "Benfica",
        "SL Benfica": "Benfica",
        "Sport Lisboa e Benfica": "Benfica",
        "Boavista": "Boavista",
        "Boavista FC": "Boavista",
        "Casa Pia": "Casa Pia",
        "Casa Pia AC": "Casa Pia",
        "Estoril": "Estoril",
        "GD Estoril Praia": "Estoril",
        "Estrela": "Estrela",
        "Estrela da Amadora": "Estrela",
        "CF Estrela da Amadora": "Estrela",
        "Famalicao": "Famalicao",
        "Famalicão": "Famalicao",
        "FC Famalicao": "Famalicao",
        "FC Famalicão": "Famalicao",
        "Farense": "Farense",
        "SC Farense": "Farense",
        "Gil Vicente": "Gil Vicente",
        "Gil Vicente FC": "Gil Vicente",
        "Guimaraes": "Guimaraes",
        "Vitória SC": "Guimaraes",
        "Vitoria SC": "Guimaraes",
        "Vitória Guimarães": "Guimaraes",
        "Vitoria Guimaraes": "Guimaraes",
        "Vitória de Guimarães": "Guimaraes",
        "Maritimo": "Maritimo",
        "CS Marítimo": "Maritimo",
        "Marítimo": "Maritimo",
        "Moreirense": "Moreirense",
        "Moreirense FC": "Moreirense",
        "Nacional": "Nacional",
        "CD Nacional": "Nacional",
        "Porto": "Porto",
        "FC Porto": "Porto",
        "Rio Ave": "Rio Ave",
        "Rio Ave FC": "Rio Ave",
        "Santa Clara": "Santa Clara",
        "CD Santa Clara": "Santa Clara",
        "Sp Braga": "Sp Braga",
        "Braga": "Sp Braga",
        "SC Braga": "Sp Braga",
        "Sporting Braga": "Sp Braga",
        "Sporting Clube de Braga": "Sp Braga",
        "Sp Lisbon": "Sp Lisbon",
        "Sporting": "Sp Lisbon",
        "Sporting CP": "Sp Lisbon",
        "Sporting Lisbon": "Sp Lisbon",
        "Sporting Clube de Portugal": "Sp Lisbon",
        "Tondela": "Tondela",
        "CD Tondela": "Tondela",
    },
    # ------------------------------------------------------------------ N1
    "N1": {
        "Ajax": "Ajax",
        "AFC Ajax": "Ajax",
        "AZ Alkmaar": "AZ Alkmaar",
        "AZ": "AZ Alkmaar",
        "Almere City": "Almere City",
        "Almere City FC": "Almere City",
        "Cambuur": "Cambuur",
        "SC Cambuur": "Cambuur",
        "SC Cambuur-Leeuwarden": "Cambuur",
        "Den Haag": "Den Haag",
        "ADO Den Haag": "Den Haag",
        "Excelsior": "Excelsior",
        "SBV Excelsior": "Excelsior",
        "Feyenoord": "Feyenoord",
        "Feyenoord Rotterdam": "Feyenoord",
        "For Sittard": "For Sittard",
        "Fortuna Sittard": "For Sittard",
        "Go Ahead Eagles": "Go Ahead Eagles",
        "Groningen": "Groningen",
        "FC Groningen": "Groningen",
        "Heerenveen": "Heerenveen",
        "SC Heerenveen": "Heerenveen",
        "Heracles": "Heracles",
        "Heracles Almelo": "Heracles",
        "NAC Breda": "NAC Breda",
        "Nijmegen": "Nijmegen",
        "NEC": "Nijmegen",
        "NEC Nijmegen": "Nijmegen",
        "PSV Eindhoven": "PSV Eindhoven",
        "PSV": "PSV Eindhoven",
        "Sparta Rotterdam": "Sparta Rotterdam",
        "Telstar": "Telstar",
        "Telstar 1963": "Telstar",
        "Twente": "Twente",
        "FC Twente": "Twente",
        "FC Twente '65": "Twente",
        "Utrecht": "Utrecht",
        "FC Utrecht": "Utrecht",
        "Volendam": "Volendam",
        "FC Volendam": "Volendam",
        "Waalwijk": "Waalwijk",
        "RKC Waalwijk": "Waalwijk",
        "Willem II": "Willem II",
        "Willem II Tilburg": "Willem II",
        "Zwolle": "Zwolle",
        "PEC Zwolle": "Zwolle",
    },
    # ------------------------------------------------------------------ E1
    "E1": {
        "Birmingham": "Birmingham",
        "Birmingham City": "Birmingham",
        "Birmingham City FC": "Birmingham",
        "Blackburn": "Blackburn",
        "Blackburn Rovers": "Blackburn",
        "Blackburn Rovers FC": "Blackburn",
        "Bolton": "Bolton",
        "Bolton Wanderers": "Bolton",
        "Bolton Wanderers FC": "Bolton",
        "Bristol City": "Bristol City",
        "Bristol City FC": "Bristol City",
        "Burnley": "Burnley",
        "Burnley FC": "Burnley",
        "Cardiff": "Cardiff",
        "Cardiff City": "Cardiff",
        "Cardiff City FC": "Cardiff",
        "Charlton": "Charlton",
        "Charlton Athletic": "Charlton",
        "Charlton Athletic FC": "Charlton",
        "Coventry": "Coventry",
        "Coventry City": "Coventry",
        "Derby": "Derby",
        "Derby County": "Derby",
        "Derby County FC": "Derby",
        "Hull": "Hull",
        "Hull City": "Hull",
        "Ipswich": "Ipswich",
        "Ipswich Town": "Ipswich",
        "Leeds": "Leeds",
        "Leeds United": "Leeds",
        "Leeds United FC": "Leeds",
        "Leicester": "Leicester",
        "Leicester City": "Leicester",
        "Lincoln": "Lincoln",
        "Lincoln City": "Lincoln",
        "Lincoln City FC": "Lincoln",
        "Luton": "Luton",
        "Luton Town": "Luton",
        "Middlesbrough": "Middlesbrough",
        "Middlesbrough FC": "Middlesbrough",
        "Millwall": "Millwall",
        "Millwall FC": "Millwall",
        "Norwich": "Norwich",
        "Norwich City": "Norwich",
        "Norwich City FC": "Norwich",
        "Oxford": "Oxford",
        "Oxford United": "Oxford",
        "Plymouth": "Plymouth",
        "Plymouth Argyle": "Plymouth",
        "Portsmouth": "Portsmouth",
        "Portsmouth FC": "Portsmouth",
        "Preston": "Preston",
        "Preston North End": "Preston",
        "Preston North End FC": "Preston",
        "QPR": "QPR",
        "Queens Park Rangers": "QPR",
        "Queens Park Rangers FC": "QPR",
        "Sheffield United": "Sheffield United",
        "Sheffield United FC": "Sheffield United",
        "Sheffield Weds": "Sheffield Weds",
        "Sheffield Wednesday": "Sheffield Weds",
        "Southampton": "Southampton",
        "Southampton FC": "Southampton",
        "Stoke": "Stoke",
        "Stoke City": "Stoke",
        "Stoke City FC": "Stoke",
        "Sunderland": "Sunderland",
        "Swansea": "Swansea",
        "Swansea City": "Swansea",
        "Swansea City AFC": "Swansea",
        "Watford": "Watford",
        "Watford FC": "Watford",
        "West Brom": "West Brom",
        "West Bromwich Albion": "West Brom",
        "West Bromwich Albion FC": "West Brom",
        "West Ham": "West Ham",
        "West Ham United": "West Ham",
        "West Ham United FC": "West Ham",
        "Wolves": "Wolves",
        "Wolverhampton Wanderers": "Wolves",
        "Wolverhampton Wanderers FC": "Wolves",
        "Wrexham": "Wrexham",
        "Wrexham AFC": "Wrexham",
    },
}

SUPPORTED_LEAGUES = ("E0", "F1", "D1", "I1", "SP1")

# Seuil de similarité difflib en dessous duquel on refuse une correspondance.
FUZZY_CUTOFF = 0.70

_HISTORICAL_CACHE: dict[tuple, list[str]] = {}

# Caractères de ponctuation neutralisés avant comparaison.
_PUNCTUATION = "'’`.-_/\\,()[]"


def normalize_name(name: str | None) -> str:
    """
    Normalise un nom d'équipe : minuscules, accents retirés, « & » -> « and »,
    ponctuation remplacée par des espaces, espaces multiples compactés.
    """
    if name is None:
        return ""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = text.replace("&", " and ")
    for ch in _PUNCTUATION:
        text = text.replace(ch, " ")
    return " ".join(text.split())


@lru_cache(maxsize=None)
def _league_index(league_code: str) -> dict[str, str]:
    """Index normalisé -> nom Football-Data pour un championnat (mis en cache)."""
    index: dict[str, str] = {}
    for api_name, fd_name in TEAM_ALIASES.get(league_code, {}).items():
        index[normalize_name(api_name)] = fd_name
    # Le nom cible lui-même doit être reconnu (ex. « Man United » tel quel).
    for fd_name in TEAM_ALIASES.get(league_code, {}).values():
        index.setdefault(normalize_name(fd_name), fd_name)
    return index


def historical_teams(league_code: str, raw_dir: str | None = None) -> list[str]:
    """
    Équipes réellement présentes dans les CSV historiques d'un championnat.

    Sert de vivier de secours pour la recherche floue lorsque le dictionnaire
    statique ne contient pas un club (cas d'un promu). Le cache est invalidé
    automatiquement si un fichier CSV est modifié (clé = mtime max).
    """
    if raw_dir is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        raw_dir = os.path.join(root, "data", "raw")

    try:
        filenames = [
            os.path.join(raw_dir, name)
            for name in os.listdir(raw_dir)
            if name.lower().endswith(f"_{league_code.lower()}.csv")
        ]
    except OSError:
        return []

    if not filenames:
        return []

    try:
        newest_mtime = max(os.path.getmtime(path) for path in filenames)
    except OSError:
        return []

    cache_key = (league_code, raw_dir, newest_mtime)
    cached = _HISTORICAL_CACHE.get(cache_key)
    if cached is not None:
        return cached

    names: set[str] = set()
    try:
        import pandas as pd

        for path in filenames:
            try:
                frame = pd.read_csv(path, usecols=lambda col: col in ("HomeTeam", "AwayTeam"))
            except Exception:
                continue
            for column in ("HomeTeam", "AwayTeam"):
                if column in frame.columns:
                    names.update(
                        str(value).strip()
                        for value in frame[column].dropna()
                        if str(value).strip()
                    )
    except Exception:
        return []

    result = sorted(names)
    _HISTORICAL_CACHE.clear()
    _HISTORICAL_CACHE[cache_key] = result
    return result


def map_team_name(
    api_name: str,
    league_code: str,
    historical: list[str] | None = None,
) -> tuple[str, str]:
    """
    Traduit un nom d'équipe The Odds API vers le nom Football-Data.

    Stratégie (dans l'ordre) :
        1. correspondance exacte après normalisation (« exact ») ;
        2. correspondance floue difflib (« fuzzy ») ;
        3. repli par sous-chaîne sur le candidat le plus long (« substring ») ;
        4. sinon, le nom d'origine est renvoyé avec la méthode « unmapped »
           (aucune exception : le pipeline continue de fonctionner).

    Args:
        api_name: nom renvoyé par The Odds API.
        league_code: code Football-Data du championnat (E0, F1, D1, I1, SP1).
        historical: vivier d'équipes optionnel (par défaut data/raw).

    Returns:
        (nom_football_data, méthode) où méthode ∈ {"exact","fuzzy","substring","unmapped"}.
    """
    if not api_name or not str(api_name).strip():
        return "", "empty"

    raw_name = str(api_name).strip()
    normalized = normalize_name(raw_name)
    if not normalized:
        return raw_name, "unmapped"

    index = _league_index(league_code)

    # 1. Correspondance exacte
    if normalized in index:
        return index[normalized], "exact"

    # Candidats : dictionnaire statique + équipes historiques réellement connues
    candidates: dict[str, str] = dict(index)
    pool = historical if historical is not None else historical_teams(league_code)
    for name in pool:
        cleaned = str(name).strip()
        if cleaned:
            candidates.setdefault(normalize_name(cleaned), cleaned)

    if not candidates:
        return raw_name, "unmapped"

    # 2. Correspondance floue (difflib)
    close = difflib.get_close_matches(normalized, list(candidates.keys()), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return candidates[close[0]], "fuzzy"

    # 3. Repli par sous-chaîne : on retient le candidat le plus long contenu
    #    dans le nom fourni (ou inversement), pour éviter « Milan » vs « Inter ».
    best: tuple[int, str] | None = None
    for candidate_norm, fd_name in candidates.items():
        if len(candidate_norm) < 6:
            continue
        if candidate_norm in normalized or normalized in candidate_norm:
            length = len(candidate_norm)
            if best is None or length > best[0]:
                best = (length, fd_name)
    if best is not None:
        return best[1], "substring"

    return raw_name, "unmapped"


def aliases_for(fd_name: str, league_code: str) -> list[str]:
    """
    Variantes de nom (côté fournisseur) associées à un nom Football-Data.

    Utile pour interroger une API qui exige un nom officiel (ex. « Bayern
    München ») alors que nos CSV utilisent un nom abrégé (« Bayern Munich »).
    Le nom Football-Data lui-même est inclus en dernier recours.
    """
    aliases = [
        api_name
        for api_name, target in TEAM_ALIASES.get(league_code, {}).items()
        if target == fd_name
    ]
    if fd_name not in aliases:
        aliases.append(fd_name)
    return aliases


def map_fixture_teams(
    home_name: str,
    away_name: str,
    league_code: str,
    historical: list[str] | None = None,
) -> dict:
    """
    Traduit les deux équipes d'une affiche et renvoie un rapport détaillé.

    Returns:
        {
          "home": nom Football-Data, "away": nom Football-Data,
          "home_method": ..., "away_method": ...,
          "unmapped": [noms non résolus],
        }
    """
    home_fd, home_method = map_team_name(home_name, league_code, historical)
    away_fd, away_method = map_team_name(away_name, league_code, historical)
    unmapped = []
    if home_method == "unmapped":
        unmapped.append(home_name)
    if away_method == "unmapped":
        unmapped.append(away_name)
    return {
        "home": home_fd,
        "away": away_fd,
        "home_method": home_method,
        "away_method": away_method,
        "unmapped": unmapped,
    }


if __name__ == "__main__":  # petit auto-test manuel
    samples = {
        "E0": ["Manchester United", "Man City", "Nottingham Forest", "Brighton and Hove Albion", "Wolverhampton Wanderers"],
        "F1": ["Paris Saint Germain", "Olympique de Marseille", "AS Saint-Etienne", "Stade Brestois 29"],
        "D1": ["Bayern München", "Borussia Mönchengladbach", "1. FC Köln", "Eintracht Frankfurt"],
        "I1": ["Inter Milan", "AC Milan", "Hellas Verona", "Juventus"],
        "SP1": ["Atlético Madrid", "Athletic Club", "Real Sociedad", "Rayo Vallecano"],
    }
    for code, names in samples.items():
        print(f"--- {code} ---")
        for name in names:
            fd, method = map_team_name(name, code)
            print(f"  {name!r:38} -> {fd!r:16} [{method}]")
