"""
backend/team_context.py - Contexte de forme d'une équipe (données internes).

Calcule, à partir de l'historique Football-Data déjà chargé, un ensemble
d'indicateurs de forme utilisés par la page détail d'un match :

  - 10 derniers matchs (résultats, buts, adversaire, lieu) ;
  - bilan global, à domicile et à l'extérieur (V/N/D, buts, points/match) ;
  - clean sheets, matchs sans marquer, taux BTTS, taux Over 2.5 ;
  - série en cours (ex. 3 victoires consécutives) ;
  - jours de repos depuis le dernier match et densité du calendrier ;
  - tendance Elo sur les 5 derniers matchs (si le moteur est fourni).

Aucune donnée externe n'est nécessaire : tout est dérivé du DataFrame
historique, donc disponible immédiatement et sans clé API.
"""

from __future__ import annotations

import pandas as pd


def _result(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "W"
    if goals_for < goals_against:
        return "L"
    return "D"


def _outcome_summary(matches: list[dict]) -> dict:
    """Bilan V/N/D, buts et points d'une liste de matchs."""
    played = len(matches)
    wins = sum(1 for m in matches if m["result"] == "W")
    draws = sum(1 for m in matches if m["result"] == "D")
    losses = played - wins - draws
    goals_for = sum(m["goals_for"] for m in matches)
    goals_against = sum(m["goals_against"] for m in matches)
    return {
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": wins * 3 + draws,
        "points_per_game": round((wins * 3 + draws) / played, 2) if played else 0.0,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_difference": goals_for - goals_against,
        "avg_goals_for": round(goals_for / played, 2) if played else 0.0,
        "avg_goals_against": round(goals_against / played, 2) if played else 0.0,
    }


def _streak(matches_desc: list[dict]) -> dict:
    """
    Série en cours : même résultat répété sur les matchs les plus récents.
    ``matches_desc`` doit être trié du plus récent au plus ancien.
    """
    if not matches_desc:
        return {"type": None, "length": 0, "label": "—"}
    first = matches_desc[0]["result"]
    length = 0
    for match in matches_desc:
        if match["result"] != first:
            break
        length += 1
    label = {"W": "victoires", "D": "nuls", "L": "défaites"}[first]
    return {"type": first, "length": length, "label": f"{length} {label}"}


def team_form_context(
    df: pd.DataFrame,
    team: str,
    before=None,
    limit: int = 10,
    engine=None,
) -> dict:
    """
    Contexte de forme d'une équipe avant une date donnée.

    Args:
        df: historique nettoyé (colonnes Date, HomeTeam, AwayTeam, FTHG, FTAG).
        team: nom Football-Data de l'équipe.
        before: date limite (exclusive). Les matchs postérieurs sont ignorés
                (aucune fuite de données).
        limit: nombre de matchs analysés (par défaut 10).
        engine: PredictionEngine optionnel, pour la tendance Elo.

    Returns:
        Dictionnaire prêt à sérialiser en JSON.
    """
    mask = (df["HomeTeam"] == team) | (df["AwayTeam"] == team)
    if before is not None:
        mask &= df["Date"] < pd.Timestamp(before)

    subset = df[mask].sort_values("Date")
    rows: list[dict] = []
    for row in subset.itertuples(index=False):
        is_home = row.HomeTeam == team
        goals_for = int(row.FTHG) if is_home else int(row.FTAG)
        goals_against = int(row.FTAG) if is_home else int(row.FTHG)
        rows.append({
            "date": pd.Timestamp(row.Date).strftime("%Y-%m-%d"),
            "opponent": row.AwayTeam if is_home else row.HomeTeam,
            "venue": "H" if is_home else "A",
            "goals_for": goals_for,
            "goals_against": goals_against,
            "result": _result(goals_for, goals_against),
            "league": str(getattr(row, "Championnat", "")),
        })

    recent = rows[-limit:]
    recent_desc = list(reversed(recent))

    home_matches = [m for m in recent if m["venue"] == "H"]
    away_matches = [m for m in recent if m["venue"] == "A"]

    clean_sheets = sum(1 for m in recent if m["goals_against"] == 0)
    failed_to_score = sum(1 for m in recent if m["goals_for"] == 0)
    btts = sum(1 for m in recent if m["goals_for"] > 0 and m["goals_against"] > 0)
    over_25 = sum(1 for m in recent if m["goals_for"] + m["goals_against"] > 2.5)

    rest_days = None
    if before is not None and rows:
        last_date = pd.Timestamp(rows[-1]["date"])
        rest_days = max(0, (pd.Timestamp(before).normalize() - last_date.normalize()).days)

    # Densité : nombre de matchs dans les 14 derniers jours précédant la rencontre
    matches_last_14 = 0
    if before is not None and rows:
        cutoff = pd.Timestamp(before) - pd.Timedelta(days=14)
        matches_last_14 = sum(1 for m in rows if pd.Timestamp(m["date"]) >= cutoff)

    # Tendance Elo : variation sur les 5 dernières entrées d'historique
    elo_trend = None
    if engine is not None:
        history = getattr(engine, "elo_history", {}).get(team, [])
        if history:
            recent_elo = [float(value) for _, value in history[-5:]]
            if len(recent_elo) >= 2:
                elo_trend = {
                    "current": round(recent_elo[-1], 1),
                    "delta_5": round(recent_elo[-1] - recent_elo[0], 1),
                }

    return {
        "team": team,
        "matches": recent_desc,
        "overall": _outcome_summary(recent),
        "home": _outcome_summary(home_matches),
        "away": _outcome_summary(away_matches),
        "clean_sheets": clean_sheets,
        "clean_sheet_rate": round(clean_sheets / len(recent) * 100, 1) if recent else 0.0,
        "failed_to_score": failed_to_score,
        "btts_count": btts,
        "btts_rate": round(btts / len(recent) * 100, 1) if recent else 0.0,
        "over_2_5_count": over_25,
        "over_2_5_rate": round(over_25 / len(recent) * 100, 1) if recent else 0.0,
        "streak": _streak(recent_desc),
        "rest_days": rest_days,
        "matches_last_14_days": matches_last_14,
        "elo_trend": elo_trend,
    }
