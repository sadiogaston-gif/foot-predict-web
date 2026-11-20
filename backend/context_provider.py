"""
backend/context_provider.py - Contexte externe (effectifs, blessures, compositions, notes).

Nos sources principales (Football-Data, OpenFootball, The Odds API) ne contiennent
NI effectifs, NI blessures, NI compositions, NI notes de joueurs. Ces informations
proviennent de deux fournisseurs, utilisés en complément :

  1. API-Football (api-sports.io) : effectifs et blessures.
     Plan gratuit : effectifs OK ; blessures limitées aux saisons 2022-2024.
  2. Highlightly (soccer.highlightly.net) : compositions et notes des joueurs
     (`matchRating`), ainsi que la résolution du match par date.

Les deux sont OPTIONNELS et indépendants :
    API_FOOTBALL_KEY=...
    HIGHLIGHTLY_API_KEY=...

Chaque section est dégradée séparément : si une source manque ou renvoie une
erreur (quota, plan, réseau), les autres continuent de fonctionner et une note
explique la raison. Aucune exception ne remonte jusqu'à l'API HTTP.

Limites assumées :
  - données non historisées chez nous : pas de backtest, pas d'impact sur les
    probabilités ;
  - compositions publiées ~1 h avant le coup d'envoi ;
  - notes disponibles après la rencontre.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
import time
import unicodedata
from datetime import date

import requests

from backend.team_mapping import aliases_for, normalize_name

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
RAPIDAPI_BASE = "https://api-football-v1.p.rapidapi.com/v3"
RAPIDAPI_HOST = "api-football-v1.p.rapidapi.com"

HIGHLIGHTLY_BASE = "https://soccer.highlightly.net"

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

# Codes Football-Data.co.uk -> codes competitions football-data.org
FOOTBALL_DATA_COMPETITIONS: dict[str, str] = {
    "E0": "PL",
    # Seule deuxième division disponible sur le plan gratuit Football-Data.org
    "E1": "ELC",
    "F1": "FL1",
    "D1": "BL1",
    "I1": "SA",
    "SP1": "PD",
    "P1": "PPL",
    "N1": "DED",
    "B1": "B1",
    "T1": "TR",
    "SC0": "SCO",
    "G1": "GRE",
    "T2": "TR2",
}

DEFAULT_TIMEOUT = 20

# Codes Football-Data -> identifiants API-Football
LEAGUE_IDS: dict[str, int] = {
    "E0": 39,
    "E1": 40,
    "F1": 61,
    "F2": 62,
    "D1": 78,
    "D2": 79,
    "I1": 135,
    "I2": 136,
    "SP1": 140,
    "SP2": 141,
    "P1": 94,
    "P2": 95,
    "N1": 88,
    "B1": 123,
    "T1": 102,
    "SC0": 172,
    "G1": 167,
    "T2": 103,
}

# Codes Football-Data -> (nom de ligue, pays) chez Highlightly
HIGHLIGHTLY_LEAGUES: dict[str, tuple[str, str]] = {
    "E0": ("Premier League", "England"),
    "E1": ("Championship", "England"),
    "F1": ("Ligue 1", "France"),
    "F2": ("Ligue 2", "France"),
    "D1": ("Bundesliga", "Germany"),
    "D2": ("2. Bundesliga", "Germany"),
    "I1": ("Serie A", "Italy"),
    "I2": ("Serie B", "Italy"),
    "SP1": ("La Liga", "Spain"),
    "SP2": ("Segunda División", "Spain"),
    "P1": ("Primeira Liga", "Portugal"),
    "P2": ("Liga Portugal 2", "Portugal"),
    "N1": ("Eredivisie", "Netherlands"),
    "B1": ("Jupiler Pro League", "Belgium"),
    "T1": ("Süper Lig", "Turkey"),
    "SC0": ("Scottish Premiership", "Scotland"),
    "G1": ("Super League", "Greece"),
    "T2": ("1. Lig", "Turkey"),
}

# Durées de cache (secondes)
TTL_TEAM = 7 * 24 * 3600
TTL_SQUAD = 7 * 24 * 3600
TTL_INJURIES = 6 * 3600
TTL_MATCH = 6 * 3600
TTL_LINEUP = 30 * 60
TTL_RATINGS = 12 * 3600
TTL_FD_TEAMS = 7 * 24 * 3600
TTL_FD_SQUAD = 7 * 24 * 3600
TTL_FD_STANDINGS = 6 * 3600

# Équipes à exclure : féminines, réserves, jeunes
_EXCLUDED_TEAM = re.compile(r"\b(W|Women|II|U\d{1,2}|Reserves?|Youth|Academy)\b", re.IGNORECASE)


def _season_year(match_date) -> int:
    if hasattr(match_date, "month"):
        return match_date.year if match_date.month >= 7 else match_date.year - 1
    return date.today().year


def _similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, normalize_name(left), normalize_name(right)).ratio()


def _ascii_search(text: str) -> str:
    """ASCII alphanumérique + espaces (contrainte de l'API-Football)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", stripped)
    return " ".join(cleaned.split())


class RateLimitError(RuntimeError):
    """Quota (par minute ou journalier) atteint chez un fournisseur."""


# ---------------------------------------------------------------------------
# API-Football : effectifs + blessures
# ---------------------------------------------------------------------------
class ApiFootballProvider:
    def __init__(self, api_key: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self.mode = (os.environ.get("API_FOOTBALL_MODE", "") or "").strip().lower() or None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _headers(mode: str, api_key: str) -> dict:
        if mode == "rapidapi":
            return {"x-rapidapi-key": api_key, "x-rapidapi-host": RAPIDAPI_HOST}
        return {"x-apisports-key": api_key}

    def _request(self, mode: str, path: str, params: dict):
        base = RAPIDAPI_BASE if mode == "rapidapi" else API_FOOTBALL_BASE
        return requests.get(
            f"{base}{path}",
            params=params,
            headers=self._headers(mode, self.api_key),
            timeout=self.timeout,
        )

    def _get(self, path: str, params: dict, ttl: int) -> dict:
        cache_key = (path, tuple(sorted((key, str(value)) for key, value in params.items())))
        cached = self._cache.get(cache_key)
        if cached is not None and (time.time() - cached[0]) < ttl:
            return cached[1]

        if self.mode is None:
            response = self._request("direct", path, params)
            if response.status_code == 200:
                self.mode = "direct"
            elif response.status_code == 403 and "invalid api key" in response.text.lower():
                rapid = self._request("rapidapi", path, params)
                if rapid.status_code == 200:
                    self.mode = "rapidapi"
                    response = rapid
                elif rapid.status_code == 403 and "not subscribed" in rapid.text.lower():
                    raise RuntimeError(
                        "clé RapidAPI valide, mais aucun abonnement à API-Football : "
                        "souscrivez au plan gratuit sur rapidapi.com."
                    )
                elif rapid.status_code == 401:
                    raise RuntimeError("clé API refusée par API-Football (direct et RapidAPI).")
                else:
                    rapid.raise_for_status()
                    response = rapid
            else:
                response.raise_for_status()
        else:
            response = self._request(self.mode, path, params)
            if response.status_code == 429:
                raise RateLimitError("limite de requêtes API-Football atteinte (429).")
            response.raise_for_status()

        payload = response.json()
        errors = payload.get("errors")
        if errors:
            raise RuntimeError(f"API-Football: {str(errors)[:200]}")

        self._cache[cache_key] = (time.time(), payload)
        return payload

    def head_to_head(self, team1_id: int, team2_id: int, last: int = 5) -> list[dict]:
        """
        Dernières confrontations directes entre deux équipes (API-Football).

        Endpoint : GET /fixtures/headtohead?h2h=id1-id2&last=N
        Retourne une liste triée du plus ancien au plus récent :
          {date, home, away, home_goals, away_goals, status}
        En cas d'erreur réseau/API, on renvoie une liste vide (jamais d'exception).
        """
        if not self.available or not team1_id or not team2_id:
            return []
        try:
            payload = self._get(
                "/fixtures/headtohead",
                {"h2h": f"{int(team1_id)}-{int(team2_id)}", "last": int(last)},
                TTL_MATCH,
            )
        except Exception:
            return []
        results = []
        for fixture in payload.get("response") or []:
            fixture_obj = fixture.get("fixture") or {}
            teams = fixture.get("teams") or {}
            goals = fixture.get("goals") or {}
            home = (teams.get("home") or {}).get("name")
            away = (teams.get("away") or {}).get("name")
            home_goals = goals.get("home")
            away_goals = goals.get("away")
            if not home or not away or home_goals is None or away_goals is None:
                continue
            results.append({
                "date": str(fixture_obj.get("date") or "")[:10],
                "home": home,
                "away": away,
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
                "status": (fixture_obj.get("status") or {}).get("short") or "FT",
            })
        return results

    def _search_terms(self, fd_name: str, league_code: str) -> list[str]:
        terms: list[str] = []
        for alias in aliases_for(fd_name, league_code):
            cleaned = _ascii_search(alias)
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
        first_word = _ascii_search(fd_name).split(" ")[0] if _ascii_search(fd_name) else ""
        if len(first_word) >= 4 and first_word not in terms:
            terms.append(first_word)
        return terms[:4]

    def _find_team(self, team_name: str, league_code: str) -> dict | None:
        """Retrouve l'équipe masculine API-Football (exclut féminines/réserves/jeunes)."""
        candidates: list[tuple[float, dict]] = []
        for term in self._search_terms(team_name, league_code):
            try:
                payload = self._get("/teams", {"search": term}, TTL_TEAM)
            except RateLimitError:
                raise
            except RuntimeError:
                continue
            for item in payload.get("response") or []:
                team = item.get("team") or {}
                name = team.get("name") or ""
                if not name or _EXCLUDED_TEAM.search(name):
                    continue
                score = _similarity(team_name, name)
                if score >= 0.5:
                    candidates.append((score, {"id": team.get("id"), "name": name}))
            # Inutile de multiplier les requêtes si un candidat très proche existe
            if candidates and max(score for score, _ in candidates) >= 0.85:
                break

        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]

    def _squad(self, team_id: int) -> list[dict] | None:
        payload = self._get("/players/squads", {"team": team_id}, TTL_SQUAD)
        blocks = payload.get("response") or []
        if not blocks:
            return None
        players = blocks[0].get("players") or []
        return [
            {
                "id": player.get("id"),
                "name": player.get("name"),
                "age": player.get("age"),
                "number": player.get("number"),
                "position": player.get("position"),
                "photo": player.get("photo"),
            }
            for player in players
        ]

    def _injuries(self, team_id: int, season: int) -> list[dict] | None:
        payload = self._get("/injuries", {"team": team_id, "season": season}, TTL_INJURIES)
        entries = payload.get("response") or []
        if not entries:
            return []
        result = []
        for entry in entries[:12]:
            player = entry.get("player") or {}
            fixture = entry.get("fixture") or {}
            result.append({
                "player": player.get("name"),
                "type": entry.get("type"),
                "reason": entry.get("reason"),
                "fixture_date": (fixture.get("date") or "")[:10] or None,
                "photo": player.get("photo"),
            })
        return result

    def get_squads_and_injuries(
        self,
        home_team: str,
        away_team: str,
        league_code: str,
        match_date,
    ) -> dict:
        """Effectifs et blessures, avec dégradation indépendante par section."""
        out = {
            "teams": {"home": None, "away": None},
            "squads": None,
            "injuries": None,
            "injuries_available": False,
            "squad_note": None,
            "injury_note": None,
        }

        try:
            home = self._find_team(home_team, league_code)
            away = self._find_team(away_team, league_code)
        except RateLimitError as exc:
            out["squad_note"] = f"Limite API-Football atteinte : {exc}"
            out["injury_note"] = out["squad_note"]
            return out
        except RuntimeError as exc:
            out["squad_note"] = str(exc)
            out["injury_note"] = str(exc)
            return out

        out["teams"] = {"home": home, "away": away}
        if not home and not away:
            out["squad_note"] = "Équipe introuvable dans API-Football."
            out["injury_note"] = out["squad_note"]
            return out

        squads = {}
        for side, team in (("home", home), ("away", away)):
            if not team:
                squads[side] = None
                continue
            try:
                squads[side] = self._squad(team["id"])
            except RateLimitError:
                squads[side] = None
            except Exception:
                squads[side] = None
        if any(squads.values()):
            out["squads"] = squads
        else:
            out["squad_note"] = "Effectifs indisponibles pour le moment."

        season = _season_year(match_date)
        injuries = {}
        plan_blocked = False
        rate_limited = False
        for side, team in (("home", home), ("away", away)):
            if not team:
                injuries[side] = None
                continue
            try:
                injuries[side] = self._injuries(team["id"], season)
            except RateLimitError:
                injuries[side] = None
                rate_limited = True
            except RuntimeError as exc:
                injuries[side] = None
                if "plan" in str(exc).lower() or "season" in str(exc).lower():
                    plan_blocked = True

        if any(value is not None for value in injuries.values()):
            out["injuries"] = injuries
            out["injuries_available"] = True
        else:
            out["injuries_available"] = False
            if rate_limited:
                out["injury_note"] = (
                    "Limite de requêtes API-Football atteinte (10/min sur le plan gratuit) : "
                    "réessayez dans une minute."
                )
            elif plan_blocked:
                out["injury_note"] = (
                    "Plan gratuit API-Football : blessures limitées aux saisons 2022-2024 "
                    "(un plan payant est nécessaire pour la saison en cours)."
                )
            else:
                out["injury_note"] = "Blessures indisponibles pour le moment."

        return out


# ---------------------------------------------------------------------------
# Highlightly : compositions + notes
# ---------------------------------------------------------------------------
class HighlightlyProvider:
    def __init__(self, api_key: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self._cache: dict[tuple, tuple[float, dict]] = {}

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict, ttl: int) -> dict | list:
        cache_key = (path, tuple(sorted((key, str(value)) for key, value in params.items())))
        cached = self._cache.get(cache_key)
        if cached is not None and (time.time() - cached[0]) < ttl:
            return cached[1]

        response = requests.get(
            f"{HIGHLIGHTLY_BASE}{path}",
            params=params,
            headers={"x-rapidapi-key": self.api_key},
            timeout=self.timeout,
        )
        if response.status_code == 429:
            raise RateLimitError("limite de requêtes Highlightly atteinte (429).")
        response.raise_for_status()
        payload = response.json()
        self._cache[cache_key] = (time.time(), payload)
        return payload

    def find_match(self, home: str, away: str, league_code: str, match_date) -> dict | None:
        league = HIGHLIGHTLY_LEAGUES.get(league_code)
        if league is None:
            return None
        league_name, country = league
        day = match_date.strftime("%Y-%m-%d") if hasattr(match_date, "strftime") else str(match_date)
        payload = self._get(
            "/matches",
            {
                "leagueName": league_name,
                "countryName": country,
                "date": day,
                "timezone": "Europe/Paris",
                "limit": 50,
            },
            TTL_MATCH,
        )

        best = None
        best_score = 0.0
        for item in payload.get("data") or []:
            home_api = (item.get("homeTeam") or {}).get("name") or ""
            away_api = (item.get("awayTeam") or {}).get("name") or ""
            score = (_similarity(home, home_api) + _similarity(away, away_api)) / 2
            if score > best_score:
                best_score = score
                best = item

        if best is None or best_score < 0.55:
            return None

        state = (best.get("state") or {}).get("description")
        score_block = (best.get("state") or {}).get("score") or {}
        return {
            "id": best.get("id"),
            "date": str(best.get("date") or "")[:10],
            "home": (best.get("homeTeam") or {}).get("name"),
            "away": (best.get("awayTeam") or {}).get("name"),
            "home_id": (best.get("homeTeam") or {}).get("id"),
            "away_id": (best.get("awayTeam") or {}).get("id"),
            "state": state,
            "score": score_block.get("current"),
        }

    def last_ratings(self, team_id: int) -> dict | None:
        """
        Notes des joueurs du dernier match terminé d'une équipe.

        Utile avant une rencontre : les notes du match en cours n'existent pas
        encore. Deux appels (last-five-games + box-score), mis en cache.
        """
        games = self._get("/last-five-games", {"teamId": team_id}, TTL_MATCH)
        if not isinstance(games, list):
            return None

        finished = [
            game
            for game in games
            if str((game.get("state") or {}).get("description", "")).startswith("Finished")
        ]
        if not finished:
            return None

        match = finished[0]
        match_id = match.get("id")
        if not match_id:
            return None

        box = self._get(f"/box-score/{match_id}", {}, TTL_RATINGS)
        if not isinstance(box, list):
            return None

        for block in box:
            team = block.get("team") or {}
            if team_id is not None and team.get("id") != team_id:
                continue
            players = []
            for entry in block.get("players") or []:
                rating = entry.get("matchRating")
                if rating in (None, "", "-"):
                    continue
                try:
                    value = float(rating)
                except (TypeError, ValueError):
                    continue
                players.append({
                    "name": entry.get("name"),
                    "rating": round(value, 1),
                    "minutes": entry.get("minutesPlayed"),
                    "position": entry.get("position"),
                })
            players.sort(key=lambda item: item["rating"], reverse=True)
            if players:
                return {
                    "team": team.get("name"),
                    "date": str(match.get("date") or "")[:10],
                    "players": players[:10],
                }
        return None

    def lineups(self, match_id: int) -> dict | None:
        payload = self._get(f"/lineups/{match_id}", {}, TTL_LINEUP)
        if not isinstance(payload, dict):
            return None
        teams = []
        for side in ("homeTeam", "awayTeam"):
            block = payload.get(side) or {}
            starters = block.get("initialLineup") or []
            teams.append({
                "team": block.get("name"),
                "formation": block.get("formation"),
                "coach": None,
                "startXI": [
                    {
                        "name": player.get("name"),
                        "number": player.get("number"),
                        "position": player.get("position"),
                    }
                    for player in starters
                ],
            })
        if not any(team["startXI"] for team in teams):
            return None
        return {"teams": teams}

    def ratings(self, match_id: int) -> dict | None:
        payload = self._get(f"/box-score/{match_id}", {}, TTL_RATINGS)
        if not isinstance(payload, list) or not payload:
            return None
        teams = []
        for block in payload:
            players = []
            for entry in block.get("players") or []:
                rating = entry.get("matchRating")
                if rating in (None, "", "-"):
                    continue
                try:
                    value = float(rating)
                except (TypeError, ValueError):
                    continue
                players.append({
                    "name": entry.get("name"),
                    "rating": round(value, 1),
                    "minutes": entry.get("minutesPlayed"),
                    "position": entry.get("position"),
                })
            players.sort(key=lambda item: item["rating"], reverse=True)
            teams.append({
                "team": (block.get("team") or {}).get("name"),
                "players": players[:12],
            })
        if not any(team["players"] for team in teams):
            return None
        return {"teams": teams}


# ---------------------------------------------------------------------------
# Football-Data.org : effectifs structurés + classement
# ---------------------------------------------------------------------------
class FootballDataProvider:
    def __init__(self, api_key: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self._cache: dict[tuple, tuple[float, dict]] = {}

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict, ttl: int) -> dict:
        cache_key = (path, tuple(sorted((key, str(value)) for key, value in params.items())))
        cached = self._cache.get(cache_key)
        if cached is not None and (time.time() - cached[0]) < ttl:
            return cached[1]

        response = requests.get(
            f"{FOOTBALL_DATA_BASE}{path}",
            params=params,
            headers={"X-Auth-Token": self.api_key},
            timeout=self.timeout,
        )
        if response.status_code == 429:
            raise RateLimitError("limite Football-Data.org atteinte (10 requêtes/min).")
        if response.status_code == 403:
            raise RuntimeError("clé Football-Data.org refusée.")
        response.raise_for_status()
        payload = response.json()
        self._cache[cache_key] = (time.time(), payload)
        return payload

    def _competition(self, league_code: str) -> str | None:
        return FOOTBALL_DATA_COMPETITIONS.get(league_code)

    def find_team(self, team_name: str, league_code: str, season: int) -> dict | None:
        competition = self._competition(league_code)
        if competition is None:
            return None
        payload = self._get(f"/competitions/{competition}/teams", {"season": season}, TTL_FD_TEAMS)
        best = None
        best_score = 0.0
        for team in payload.get("teams") or []:
            name = team.get("name") or ""
            short = team.get("shortName") or ""
            tla = team.get("tla") or ""
            score = max(_similarity(team_name, name), _similarity(team_name, short))
            if tla and normalize_name(team_name) == normalize_name(tla):
                score = 1.0
            if score > best_score:
                best_score = score
                best = team
        if best is None or best_score < 0.5:
            return None
        return {"id": best.get("id"), "name": best.get("name"), "shortName": best.get("shortName")}

    def squad(self, team_id: int) -> list[dict] | None:
        payload = self._get(f"/teams/{team_id}", {}, TTL_FD_SQUAD)
        squad = payload.get("squad") or []
        if not squad:
            return None
        players = []
        for player in squad:
            born_raw = player.get("dateOfBirth")
            age = None
            if born_raw:
                try:
                    born = date.fromisoformat(str(born_raw)[:10])
                    today = date.today()
                    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
                except ValueError:
                    age = None
            players.append({
                "id": player.get("id"),
                "name": player.get("name"),
                "age": age,
                "number": player.get("shirtNumber"),
                "position": player.get("position"),
                "photo": None,
                "nationality": player.get("nationality"),
            })
        return players

    def standings(self, league_code: str, season: int) -> list[dict] | None:
        competition = self._competition(league_code)
        if competition is None:
            return None
        payload = self._get(f"/competitions/{competition}/standings", {"season": season}, TTL_FD_STANDINGS)
        tables = payload.get("standings") or []
        if not tables:
            return None
        rows = tables[0].get("table") or []
        result = []
        for row in rows:
            team = row.get("team") or {}
            result.append({
                "position": row.get("position"),
                "team": team.get("name"),
                "team_id": team.get("id"),
                "played": row.get("playedGames"),
                "points": row.get("points"),
                "won": row.get("won"),
                "draw": row.get("draw"),
                "lost": row.get("lost"),
                "goal_difference": row.get("goalDifference"),
                "form": row.get("form"),
            })
        return result

    @staticmethod
    def match_standing(team_name: str, table: list[dict] | None) -> dict | None:
        best = None
        best_score = 0.0
        for row in table or []:
            score = _similarity(team_name, row.get("team") or "")
            if score > best_score:
                best_score = score
                best = row
        return best if best_score >= 0.5 else None


# ---------------------------------------------------------------------------
# Orchestrateur : fusionne les deux fournisseurs
# ---------------------------------------------------------------------------
class MatchContextProvider:
    def __init__(
        self,
        api_football_key: str | None = None,
        highlightly_key: str | None = None,
        football_data_key: str | None = None,
    ):
        self.api_football = ApiFootballProvider(api_football_key) if (api_football_key or "").strip() else None
        self.highlightly = HighlightlyProvider(highlightly_key) if (highlightly_key or "").strip() else None
        self.football_data = FootballDataProvider(football_data_key) if (football_data_key or "").strip() else None

    @property
    def available(self) -> bool:
        return bool(self.api_football or self.highlightly or self.football_data)

    def get_match_context(
        self,
        home_team: str,
        away_team: str,
        league_code: str,
        match_date,
    ) -> dict:
        result = {
            "available": False,
            "provider": "+".join(
                name
                for name, configured in (
                    ("football-data.org", self.football_data),
                    ("api-football", self.api_football),
                    ("highlightly", self.highlightly),
                )
                if configured is not None
            ) or "none",
            "season": _season_year(match_date),
            "teams": {"home": None, "away": None},
            "fixture": None,
            "h2h": None,
            "squads": None,
            "injuries": None,
            "lineups": None,
            "ratings": None,
            "last_ratings": None,
            "standings": None,
            "injuries_available": False,
            "lineups_available": False,
            "ratings_available": False,
            "notes": {
                "squads": None,
                "injuries": None,
                "lineups": None,
                "ratings": None,
                "standings": None,
            },
            "reason": None,
        }

        # 0) Effectifs + classement (Football-Data.org)
        season = _season_year(match_date)
        if self.football_data is not None:
            try:
                squads = {}
                for side, team_name in (("home", home_team), ("away", away_team)):
                    team = self.football_data.find_team(team_name, league_code, season)
                    squads[side] = self.football_data.squad(team["id"]) if team else None
                if any(squads.values()):
                    result["squads"] = squads
            except Exception as exc:
                logging.warning("[CONTEXT] Football-Data.org (effectifs) : %s", exc)
                result["notes"]["squads"] = f"Football-Data.org indisponible : {exc}"

            try:
                table = self.football_data.standings(league_code, season)
                home_row = self.football_data.match_standing(home_team, table)
                away_row = self.football_data.match_standing(away_team, table)
                if home_row or away_row:
                    result["standings"] = {"home": home_row, "away": away_row}
            except Exception as exc:
                logging.warning("[CONTEXT] Football-Data.org (classement) : %s", exc)
                result["notes"]["standings"] = f"Classement indisponible : {exc}"
        else:
            result["notes"]["standings"] = "FOOTBALL_DATA_KEY non configurée (classement)."

        # 1) Blessures + effectifs de secours (API-Football)
        if self.api_football is not None:
            try:
                af_data = self.api_football.get_squads_and_injuries(
                    home_team, away_team, league_code, match_date
                )
                result["teams"] = af_data["teams"]
                if result["squads"] is None:
                    result["squads"] = af_data["squads"]
                    result["notes"]["squads"] = af_data["squad_note"]
                result["injuries"] = af_data["injuries"]
                result["injuries_available"] = af_data["injuries_available"]
                result["notes"]["injuries"] = af_data["injury_note"]
            except Exception as exc:
                logging.warning("[CONTEXT] API-Football indisponible : %s", exc)
                result["notes"]["injuries"] = f"API-Football indisponible : {exc}"
                if result["squads"] is None:
                    result["notes"]["squads"] = result["notes"]["injuries"]
        else:
            if result["squads"] is None:
                result["notes"]["squads"] = "Aucune source d'effectifs configurée."
            result["notes"]["injuries"] = "API_FOOTBALL_KEY non configurée (blessures)."

        # 1b) Confrontations directes (API-Football H2H)
        if self.api_football is not None and result["teams"].get("home") and result["teams"].get("away"):
            try:
                h2h = self.api_football.head_to_head(
                    result["teams"]["home"]["id"],
                    result["teams"]["away"]["id"],
                    last=5,
                )
                if h2h:
                    result["h2h"] = h2h
            except Exception:
                pass  # le H2H reste optionnel, on ne casse pas le contexte

        # 2) Compositions + notes (Highlightly)
        if self.highlightly is not None:
            try:
                fixture = self.highlightly.find_match(home_team, away_team, league_code, match_date)
            except Exception as exc:
                logging.warning("[CONTEXT] Highlightly indisponible : %s", exc)
                fixture = None
                result["notes"]["lineups"] = f"Highlightly indisponible : {exc}"
                result["notes"]["ratings"] = result["notes"]["lineups"]

            if fixture is None:
                result["notes"]["lineups"] = result["notes"]["lineups"] or (
                    "Match introuvable chez Highlightly."
                )
                result["notes"]["ratings"] = result["notes"]["ratings"] or (
                    "Match introuvable chez Highlightly."
                )
            else:
                result["fixture"] = fixture
                try:
                    lineups = self.highlightly.lineups(fixture["id"])
                except Exception as exc:
                    lineups = None
                    result["notes"]["lineups"] = f"Compositions indisponibles : {exc}"
                if lineups:
                    result["lineups"] = lineups
                    result["lineups_available"] = True
                else:
                    result["notes"]["lineups"] = (
                        "Compositions non publiées (elles le sont ~1 h avant le coup d'envoi)."
                    )

                finished = str(fixture.get("state") or "").startswith("Finished")
                if finished:
                    try:
                        ratings = self.highlightly.ratings(fixture["id"])
                    except Exception as exc:
                        ratings = None
                        result["notes"]["ratings"] = f"Notes indisponibles : {exc}"
                    if ratings:
                        result["ratings"] = ratings
                        result["ratings_available"] = True
                    else:
                        result["notes"]["ratings"] = "Notes indisponibles pour ce match."
                else:
                    # Match à venir : on affiche les notes du dernier match de chaque équipe
                    previous = {"home": None, "away": None}
                    for side, team_id in (("home", fixture.get("home_id")), ("away", fixture.get("away_id"))):
                        if not team_id:
                            continue
                        try:
                            previous[side] = self.highlightly.last_ratings(team_id)
                        except Exception:
                            previous[side] = None
                    if any(previous.values()):
                        result["last_ratings"] = previous
                        result["notes"]["ratings"] = (
                            "Notes du dernier match : celles du match à venir ne seront "
                            "publiées qu'après la rencontre."
                        )
                    else:
                        result["notes"]["ratings"] = "Notes disponibles après la rencontre."
        else:
            result["notes"]["lineups"] = "HIGHLIGHTLY_API_KEY non configurée (compositions)."
            result["notes"]["ratings"] = "HIGHLIGHTLY_API_KEY non configurée (notes)."

        result["available"] = any(
            value is not None
            for value in (
                result["squads"],
                result["injuries"],
                result["lineups"],
                result["ratings"],
                result["last_ratings"],
                result["standings"],
            )
        )
        if not result["available"]:
            reasons = [note for note in result["notes"].values() if note]
            result["reason"] = " · ".join(dict.fromkeys(reasons)) or "Aucune source externe configurée."
        return result


_provider: MatchContextProvider | None = None


def get_provider() -> MatchContextProvider:
    """Provider singleton configuré via API_FOOTBALL_KEY et HIGHLIGHTLY_API_KEY."""
    global _provider
    if _provider is None:
        _provider = MatchContextProvider(
            os.environ.get("API_FOOTBALL_KEY", ""),
            os.environ.get("HIGHLIGHTLY_API_KEY", ""),
            os.environ.get("FOOTBALL_DATA_KEY", ""),
        )
    return _provider
