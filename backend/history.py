"""
backend/history.py - Historique « pronostics vs résultats » par journée.

Pour chaque journée (date) passée d'un championnat, reconstruit les prédictions
du moteur TELLES QU'ELLES AURAIENT ÉTÉ FAITES AVANT LES MATCHS, puis les compare
aux résultats réels :

  - parcours chronologique strict (aucune fuite de données) : tous les matchs
    d'une même date sont prédits avant que le moindre résultat de cette date
    soit injecté dans le moteur ;
  - probabilités 1X2 calibrées, pronostic (issue la plus probable), résultat
    réel, juste/faux, Brier Score par match ;
  - cotes Bet365 (ou moyenne du marché) et EV par marché lorsqu'elles existent ;
  - synthèse par journée : nombre de matchs, précision, Brier moyen, value bets.

Le calcul est mis en cache mémoire et sur disque (data/history/), invalidé dès
que les CSV historiques changent.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from prediction_engine import PredictionEngine  # noqa: E402

from config import (  # noqa: E402
    CALIBRATION_ENABLED,
    CALIBRATION_FILE,
    USE_PER_LEAGUE_ENGINES,
    USE_XG,
)


def _load_calibrator():
    """Calibrateur isotonique optionnel (config.CALIBRATION_ENABLED)."""
    if not CALIBRATION_ENABLED:
        return None
    try:
        from calibration import load

        path = CALIBRATION_FILE
        if not os.path.isabs(path):
            path = os.path.join(ROOT, path)
        return load(path)
    except Exception:
        return None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CACHE_DIR = os.path.join(DATA_DIR, "history")

LEAGUE_NAMES = {
    "E0": "Premier League (Angleterre)",
    "E1": "Championship (Angleterre)",
    "F1": "Ligue 1 (France)",
    "F2": "Ligue 2 (France)",
    "D1": "Bundesliga (Allemagne)",
    "D2": "2. Bundesliga (Allemagne)",
    "I1": "Serie A (Italie)",
    "I2": "Serie B (Italie)",
    "SP1": "La Liga (Espagne)",
    "SP2": "Segunda División (Espagne)",
    "P1": "Primeira Liga (Portugal)",
    "P2": "Liga Portugal 2 (Portugal)",
    "N1": "Eredivisie (Pays-Bas)",
    "B1": "Jupiler Pro League (Belgique)",
    "T1": "Süper Lig (Turquie)",
    "SC0": "Scottish Premiership (Écosse)",
    "G1": "Super League (Grèce)",
    "T2": "1. Lig (Turquie)",
}

MARKET_LABELS = {
    "home": "Victoire domicile",
    "draw": "Match nul",
    "away": "Victoire extérieur",
}

VALUE_MIN_EV = 0.05
VALUE_MIN_ODDS = 1.40
VALUE_MAX_ODDS = 5.00

_LOCK = threading.Lock()
_MEMORY_CACHE: dict[tuple, dict] = {}


def _raw_signature() -> str:
    """Signature des CSV historiques (invalidité du cache si données mises à jour)."""
    try:
        mtimes = [
            os.path.getmtime(os.path.join(RAW_DIR, name))
            for name in os.listdir(RAW_DIR)
            if name.lower().endswith(".csv")
        ]
    except OSError:
        return "0"
    config_tag = f"{int(USE_PER_LEAGUE_ENGINES)}:{int(CALIBRATION_ENABLED)}:{int(USE_XG)}:v3"
    return f"{max(mtimes) if mtimes else 0}:{len(mtimes)}:{config_tag}"


def _result_label(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "home"
    if goals_for < goals_against:
        return "away"
    return "draw"


def _brier(prob_home: float, prob_draw: float, prob_away: float, actual: str) -> float:
    target = {"home": (1.0, 0.0, 0.0), "draw": (0.0, 1.0, 0.0), "away": (0.0, 0.0, 1.0)}[actual]
    return (
        (prob_home - target[0]) ** 2
        + (prob_draw - target[1]) ** 2
        + (prob_away - target[2]) ** 2
    )


def _market_odds(row) -> dict:
    """Cotes 1X2 disponibles : Bet365 d'abord, moyenne du marché en repli."""
    odds = {"home": None, "draw": None, "away": None}
    for market, columns in (
        ("home", ("B365H", "AvgH")),
        ("draw", ("B365D", "AvgD")),
        ("away", ("B365A", "AvgA")),
    ):
        for column in columns:
            value = getattr(row, column, None)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if pd.notna(numeric) and numeric > 1.0:
                odds[market] = round(numeric, 3)
                break
    return odds


def _cluster_dates(dates: list[pd.Timestamp], max_gap_days: int = 1) -> list[list[pd.Timestamp]]:
    """
    Regroupe des dates consécutives en « journées ».

    Un écart de plus d'un jour marque une nouvelle journée : cela sépare les
    tours de milieu de semaine (mar/mer) des week-ends (ven/sam/dim), sans
    éclater un week-end classique (jours consécutifs).
    """
    clusters: list[list[pd.Timestamp]] = []
    for day in sorted(dates):
        if clusters and (day - clusters[-1][-1]).days <= max_gap_days:
            clusters[-1].append(day)
        else:
            clusters.append([day])
    return clusters


def build_league_history(df: pd.DataFrame, league_code: str, limit: int = 6) -> list[dict]:
    """
    Reconstruit les `limit` dernières journées d'un championnat avec prédictions
    (calculées avant les matchs) et résultats réels.

    Une « journée » regroupe les dates d'un même week-end (ex. vendredi → dimanche).

    Returns:
        Liste de journées triées de la plus récente à la plus ancienne.
    """
    league = df[df["CodeChampionnat"] == league_code].sort_values("Date")
    if league.empty:
        return []

    league_dates = sorted(league["Date"].dt.normalize().unique())
    clusters = _cluster_dates(league_dates)
    selected = clusters[-limit:]
    start = pd.Timestamp(selected[0][0])

    # Warm-up complet : tout ce qui précède la fenêtre
    calibrator = _load_calibrator()
    engine = PredictionEngine()
    if USE_PER_LEAGUE_ENGINES:
        # Modèle dédié au championnat (Brier légèrement meilleur, cf. evaluate_models)
        source = league
        engine.train(league, cutoff_date=start)
    else:
        source = df
        engine.train(df, cutoff_date=start)
    if calibrator is not None:
        engine.set_calibrator(calibrator)

    # Index date -> journée sélectionnée
    cluster_of: dict[pd.Timestamp, int] = {}
    for index, cluster in enumerate(selected):
        for day in cluster:
            cluster_of[pd.Timestamp(day)] = index

    source = source.sort_values("Date").reset_index(drop=True)
    has_xg = USE_XG and "HxG" in source.columns and "AxG" in source.columns
    window = source[source["Date"] >= start].sort_values("Date").reset_index(drop=True)
    buckets: list[list[dict]] = [[] for _ in selected]

    for day, group in window.groupby(window["Date"].dt.normalize(), sort=True):
        day_ts = pd.Timestamp(day)
        bucket_index = cluster_of.get(day_ts)

        # 1) Prédire tous les matchs du jour avec l'état d'avant-journée
        for row in group.itertuples(index=False):
            if row.CodeChampionnat != league_code:
                continue
            prob_home, prob_draw, prob_away = engine.predict_1x2(row.HomeTeam, row.AwayTeam)
            actual = _result_label(int(row.FTHG), int(row.FTAG))
            probabilities = {
                "home": round(prob_home * 100, 1),
                "draw": round(prob_draw * 100, 1),
                "away": round(prob_away * 100, 1),
            }
            predicted = max(
                (("home", prob_home), ("draw", prob_draw), ("away", prob_away)),
                key=lambda item: item[1],
            )[0]

            odds = _market_odds(row)
            ev_percent: dict[str, float | None] = {}
            best_value = None
            for market, probability in (
                ("home", prob_home),
                ("draw", prob_draw),
                ("away", prob_away),
            ):
                price = odds.get(market)
                if price is None:
                    ev_percent[market] = None
                    continue
                value = (probability * price - 1.0) * 100.0
                ev_percent[market] = round(value, 1)
                qualifies = (
                    value >= VALUE_MIN_EV * 100.0
                    and VALUE_MIN_ODDS <= price <= VALUE_MAX_ODDS
                )
                if qualifies and (best_value is None or value > best_value["ev_percent"]):
                    best_value = {
                        "market": market,
                        "label": MARKET_LABELS[market],
                        "book_odds": price,
                        "model_probability": round(probability * 100, 1),
                        "ev_percent": round(value, 1),
                    }

            record = {
                "date": str(day_ts.date()),
                "home_team": row.HomeTeam,
                "away_team": row.AwayTeam,
                "score": {"home": int(row.FTHG), "away": int(row.FTAG)},
                "probabilities": probabilities,
                "predicted": predicted,
                "predicted_probability": round(
                    {"home": prob_home, "draw": prob_draw, "away": prob_away}[predicted] * 100, 1
                ),
                "actual": actual,
                "correct": predicted == actual,
                "brier": round(_brier(prob_home, prob_draw, prob_away, actual), 4),
                "odds": odds if any(value is not None for value in odds.values()) else None,
                "ev_percent": ev_percent if any(value is not None for value in ev_percent.values()) else None,
                "best_value": best_value,
            }
            if bucket_index is not None:
                buckets[bucket_index].append(record)

        # 2) Injecter les résultats du jour (toutes ligues) pour la suite
        for row in group.itertuples(index=False):
            engine.update_match(
                row.HomeTeam,
                row.AwayTeam,
                int(row.FTHG),
                int(row.FTAG),
                row.Date,
                xgh=getattr(row, "HxG", None) if has_xg else None,
                xga=getattr(row, "AxG", None) if has_xg else None,
            )

    matchdays: list[dict] = []
    for cluster, predictions in zip(selected, buckets):
        if not predictions:
            continue
        predictions.sort(key=lambda item: (item["date"], item["home_team"]))
        correct = sum(1 for item in predictions if item["correct"])
        brier_avg = sum(item["brier"] for item in predictions) / len(predictions)
        value_bets = [item for item in predictions if item["best_value"]]
        value_hits = sum(
            1 for item in value_bets if item["best_value"]["market"] == item["actual"]
        )
        date_from = str(pd.Timestamp(cluster[0]).date())
        date_to = str(pd.Timestamp(cluster[-1]).date())
        label = date_from if date_from == date_to else f"{date_from} → {date_to}"

        matchdays.append({
            "date": date_to,          # identifiant stable (fin de journée)
            "date_from": date_from,
            "date_to": date_to,
            "label": label,
            "league": league_code,
            "league_name": LEAGUE_NAMES.get(league_code, league_code),
            "matches": predictions,
            "summary": {
                "count": len(predictions),
                "correct": correct,
                "accuracy_percent": round(correct / len(predictions) * 100, 1),
                "brier_avg": round(brier_avg, 4),
                "value_bets": len(value_bets),
                "value_hits": value_hits,
            },
        })

    matchdays.sort(key=lambda item: item["date"], reverse=True)
    return matchdays


def build_history_cached(df: pd.DataFrame, league_code: str, limit: int = 6) -> dict:
    """Historique d'un championnat, avec cache mémoire + disque."""
    signature = _raw_signature()
    key = (league_code, limit, signature)
    cached = _MEMORY_CACHE.get(key)
    if cached is not None:
        return cached

    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"history_{league_code}_{limit}.json")

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("signature") == signature:
                _MEMORY_CACHE[key] = payload
                return payload
        except Exception:
            pass

    with _LOCK:
        matchdays = build_league_history(df, league_code, limit)
        payload = {
            "league": league_code,
            "league_name": LEAGUE_NAMES.get(league_code, league_code),
            "limit": limit,
            "signature": signature,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "matchdays": matchdays,
        }
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    _MEMORY_CACHE[key] = payload
    return payload
