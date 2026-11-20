"""
backend/simulation.py - Simulateur de classement (Monte Carlo).

Projette le classement final d'un championnat à partir de :
  1. Le classement actuel (calculé depuis les CSV de la saison en cours) ;
  2. Le calendrier RESTANT complet (OpenFootball, sans filtre d'horizon) ;
  3. Les probabilités 1X2 du moteur pour chaque affiche.

Méthode (niveau 1 — probabilités figées) :
  Pour chaque scénario, on tire le résultat de chaque match restant selon les
  probabilités du modèle, on attribue 3/1/0 points, puis on classe. Après N
  scénarios, on obtient pour chaque équipe : position moyenne, distribution des
  positions, probabilités de titre / top 4 / relégation.

Les probabilités sont figées (Elo actuel, sans ré-évaluation match par match) :
le résultat est une projection indicative, pas une prévision déterministe.
"""

from __future__ import annotations

import math
import os
import time
from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd

from backend.fixtures_openfootball import LEAGUE_FILES, current_season_label, _load_league
from backend.team_mapping import map_fixture_teams
from backend.service import service
from config import SEASONS

# Ligues avec calendrier OpenFootball complet
SUPPORTED = tuple(LEAGUE_FILES.keys())

# Barème et zones
POINTS_WIN = 3
POINTS_DRAW = 1
TITLE_SPOTS = 1
TOP4_SPOTS = 4
RELEGATION_SPOTS = 3  # approximation : 3 derniers (à adapter par ligue)

# Cache mémoire : la simulation ne change pas d'une requête à l'autre.
_CACHE_TTL = 3600  # 1 heure
_cache: dict[tuple[str, int], tuple[float, dict]] = {}


def _current_table(league_code: str) -> dict[str, dict]:
    """Classement actuel depuis les CSV de la saison en cours (2627)."""
    season = SEASONS[-1]
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "raw", f"{season}_{league_code}.csv",
    )
    table: dict[str, dict] = {}
    if not os.path.exists(path):
        return table
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    for row in df.to_dict(orient="records"):
        home = str(row.get("HomeTeam") or "").strip()
        away = str(row.get("AwayTeam") or "").strip()
        fthg, ftag = row.get("FTHG"), row.get("FTAG")
        if pd.isna(fthg) or pd.isna(ftag):
            continue
        fthg, ftag = int(fthg), int(ftag)
        for team, gf, ga in ((home, fthg, ftag), (away, ftag, fthg)):
            if not team:
                continue
            entry = table.setdefault(team, {"played": 0, "points": 0, "gf": 0, "ga": 0})
            entry["played"] += 1
            entry["gf"] += gf
            entry["ga"] += ga
            if gf > ga:
                entry["points"] += POINTS_WIN
            elif gf == ga:
                entry["points"] += POINTS_DRAW
    return table


def _remaining_fixtures(league_code: str) -> list[dict]:
    """Calendrier restant complet (matchs sans score) depuis OpenFootball."""
    season = current_season_label()
    filename = LEAGUE_FILES[league_code]
    payload = _load_league(season, filename, force_refresh=False)
    if payload is None:
        return []
    today = date.today().isoformat()
    fixtures = []
    for match in payload.get("matches", []):
        raw_date = str(match.get("date") or "")[:10]
        if not raw_date or raw_date < today or match.get("score"):
            continue
        mapping = map_fixture_teams(
            str(match.get("team1", "")), str(match.get("team2", "")), league_code
        )
        home = mapping["home"] or str(match.get("team1", "")).strip()
        away = mapping["away"] or str(match.get("team2", "")).strip()
        if home and away:
            fixtures.append({"home": home, "away": away, "date": raw_date})
    return fixtures


def simulate(league_code: str, scenarios: int = 10000) -> dict:
    """Lance la simulation Monte Carlo pour un championnat (avec cache 1 h)."""
    league_code = league_code.strip().upper()
    if league_code not in SUPPORTED:
        return {"available": False, "reason": f"Calendrier complet indisponible pour {league_code}."}

    scenarios = int(max(100, min(scenarios, 50000)))
    cache_key = (league_code, scenarios)
    cached = _cache.get(cache_key)
    if cached is not None and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]

    table = _current_table(league_code)
    if not table:
        result = {"available": False, "reason": "Classement actuel indisponible (données 2627 manquantes)."}
        _cache[cache_key] = (time.time(), result)
        return result

    fixtures = _remaining_fixtures(league_code)
    if not fixtures:
        result = {"available": False, "reason": "Aucun match restant dans le calendrier."}
        _cache[cache_key] = (time.time(), result)
        return result

    teams = sorted(table.keys())
    n_teams = len(teams)
    idx = {team: i for i, team in enumerate(teams)}

    # Probabilités 1X2 figées pour chaque affiche.
    engine = service.engine_for(league_code)
    outcomes = []  # (i_home, i_away, [p_home, p_draw, p_away])
    skipped = 0
    for match in fixtures:
        home, away = match["home"], match["away"]
        if home not in idx or away not in idx:
            skipped += 1
            continue
        probs = engine.predict_match(home, away)
        p = [probs["prob_home"], probs["prob_draw"], probs["prob_away"]]
        total = sum(p)
        if total <= 0:
            skipped += 1
            continue
        outcomes.append((idx[home], idx[away], [v / total for v in p]))

    # Points de départ
    base_points = np.array([table[t]["points"] for t in teams], dtype=float)

    rng = np.random.default_rng()
    n_outcomes = len(outcomes)
    n_scenarios = int(max(100, min(scenarios, 50000)))

    # Matrice (n_scenarios, n_teams) de points — un seul tirage par match.
    # 0 = home win, 1 = draw, 2 = away win
    sim_points = np.tile(base_points, (n_scenarios, 1))
    for h, a, probs in outcomes:
        draws = rng.choice(3, size=n_scenarios, p=probs)
        sim_points[:, h] += (draws == 0) * POINTS_WIN + (draws == 1) * POINTS_DRAW
        sim_points[:, a] += (draws == 2) * POINTS_WIN + (draws == 1) * POINTS_DRAW

    position_counts = np.zeros((n_teams, n_teams), dtype=np.int64)  # [team, position]
    rank_sum = np.zeros(n_teams, dtype=float)

    # Classement : argsort décroissant des points (avec départage par index = ordre alpha)
    order = np.argsort(-sim_points, axis=1, kind="stable")
    positions = np.empty_like(order)
    rows = np.arange(n_scenarios)[:, None]
    positions[rows, order] = np.arange(n_teams)[None, :]

    for i in range(n_teams):
        position_counts[i] = np.bincount(positions[:, i], minlength=n_teams)
        rank_sum[i] = float(np.mean(positions[:, i]) + 1)

    # Agrégation par équipe
    relegation_start = max(0, n_teams - RELEGATION_SPOTS)
    standings = []
    for i, team in enumerate(teams):
        probs_pos = (position_counts[i] / n_scenarios * 100).round(2).tolist()
        standings.append({
            "team": team,
            "current_points": int(base_points[i]),
            "projected_points": round(float(np.mean(sim_points[:, i])), 1),
            "avg_position": round(rank_sum[i], 2),
            "position_probabilities": probs_pos,
            "title_probability": round(probs_pos[0], 2),
            "top4_probability": round(sum(probs_pos[:TOP4_SPOTS]), 2),
            "relegation_probability": round(sum(probs_pos[relegation_start:]), 2),
        })

    standings.sort(key=lambda r: r["avg_position"])

    result = {
        "available": True,
        "league_code": league_code,
        "scenarios": n_scenarios,
        "teams": n_teams,
        "remaining_matches": n_outcomes,
        "skipped_matches": skipped,
        # Une « journée » = chaque équipe joue un match : le nombre de matchs
        # joués par l'équipe ayant le plus joué donne la journée courante.
        "current_matchday": max((t["played"] for t in table.values()), default=0),
        "title_spots": TITLE_SPOTS,
        "top4_spots": TOP4_SPOTS,
        "relegation_spots": RELEGATION_SPOTS,
        "note": (
            f"Projection Monte Carlo sur {n_scenarios:,} scénarios. "
            "Probabilités 1X2 figées (Elo actuel), sans ré-évaluation match par match. "
            "Barème : 3 pts victoire, 1 pt nul. Départage à curseur alphabétique."
        ),
        "standings": standings,
    }
    _cache[cache_key] = (time.time(), result)
    return result
