"""
evaluate_models.py - Compare les variantes de calibration et de granularité.

Protocole rigoureux (aucune fuite de données) :
  - les calibrateurs sont APPRIS sur la saison 2024-25 (walk-forward) ;
  - l'évaluation est faite sur la saison 2025-26 (walk-forward également) ;
  - chaque match est prédit avant l'injection des résultats du jour.

Variantes comparées :
  1. pooled_raw            : modèle unique (5 ligues), probabilités brutes
  2. pooled_alpha          : modèle unique + mélange actuel vers les fréquences
  3. pooled_iso            : modèle unique + isotonique (apprise sur 2425)
  4. per_league_alpha      : un modèle par championnat + mélange alpha
  5. per_league_iso        : un modèle par championnat + isotonique par ligue

Sortie : tableau console + data/model_comparison.json
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.env import load_dotenv

load_dotenv()

from calibration import Calibrated1X2, save  # noqa: E402
from data_loader import fetch_and_clean  # noqa: E402
from prediction_engine import PredictionEngine  # noqa: E402

FIT_SEASON = "2425"
EVAL_SEASON = "2526"
OUT_PATH = os.path.join("data", "model_comparison.json")
CALIBRATION_PATH = os.path.join("models", "calibration.json")


def _actual(fthg, ftag) -> int:
    if fthg > ftag:
        return 0
    if fthg == ftag:
        return 1
    return 2


def _predict_engine(engine: PredictionEngine, row):
    raw = engine.predict_1x2_raw(row.HomeTeam, row.AwayTeam)
    alpha = engine._calibrate_1x2(*raw)
    return raw, alpha


def walk_forward_pooled(df, season: str) -> list[dict]:
    """Un seul moteur (toutes ligues), parcours chronologique de la saison."""
    target = df[df["Saison"] == season]
    if target.empty:
        return []

    ordered = df.sort_values("Date").reset_index(drop=True)
    date_series = ordered["Date"].dt.normalize()
    engine = PredictionEngine()
    engine.train(ordered, cutoff_date=target["Date"].min())

    records: list[dict] = []
    for day in sorted(target["Date"].dt.normalize().unique()):
        group = ordered[date_series == day]
        for row in group.itertuples(index=False):
            if row.Saison != season:
                continue
            raw, alpha = _predict_engine(engine, row)
            records.append({
                "league": row.CodeChampionnat,
                "raw": raw,
                "alpha": alpha,
                "actual": _actual(int(row.FTHG), int(row.FTAG)),
            })
        for row in group.itertuples(index=False):
            engine.update_match(
                row.HomeTeam, row.AwayTeam, int(row.FTHG), int(row.FTAG), row.Date
            )
    return records


def walk_forward_per_league(df, season: str) -> list[dict]:
    """Un moteur par championnat, chacun entraîné uniquement sur sa ligue."""
    records: list[dict] = []
    for code, subset in df.groupby("CodeChampionnat"):
        target = subset[subset["Saison"] == season]
        if target.empty:
            continue
        ordered = subset.sort_values("Date").reset_index(drop=True)
        date_series = ordered["Date"].dt.normalize()
        engine = PredictionEngine()
        engine.train(ordered, cutoff_date=target["Date"].min())

        for day in sorted(target["Date"].dt.normalize().unique()):
            group = ordered[date_series == day]
            for row in group.itertuples(index=False):
                if row.Saison != season:
                    continue
                raw, alpha = _predict_engine(engine, row)
                records.append({
                    "league": code,
                    "raw": raw,
                    "alpha": alpha,
                    "actual": _actual(int(row.FTHG), int(row.FTAG)),
                })
            for row in group.itertuples(index=False):
                engine.update_match(
                    row.HomeTeam, row.AwayTeam, int(row.FTHG), int(row.FTAG), row.Date
                )
    return records


def _one_hot(actual: int) -> tuple[float, float, float]:
    return {0: (1.0, 0.0, 0.0), 1: (0.0, 1.0, 0.0), 2: (0.0, 0.0, 1.0)}[actual]


def brier(probs: np.ndarray, actuals: list[int]) -> float:
    total = 0.0
    for row, actual in zip(probs, actuals):
        target = _one_hot(actual)
        total += sum((float(row[i]) - target[i]) ** 2 for i in range(3))
    return total / len(actuals)


def log_loss(probs: np.ndarray, actuals: list[int]) -> float:
    total = 0.0
    for row, actual in zip(probs, actuals):
        total -= math.log(max(float(row[actual]), 1e-12))
    return total / len(actuals)


def summarize(records: list[dict], probs: np.ndarray) -> dict:
    actuals = [record["actual"] for record in records]
    by_league: dict[str, dict] = {}
    for code in sorted({record["league"] for record in records}):
        indices = [i for i, record in enumerate(records) if record["league"] == code]
        league_probs = probs[indices]
        league_actuals = [actuals[i] for i in indices]
        by_league[code] = {
            "matches": len(indices),
            "brier": round(brier(league_probs, league_actuals), 4),
            "logloss": round(log_loss(league_probs, league_actuals), 4),
        }
    return {
        "matches": len(records),
        "brier": round(brier(probs, actuals), 4),
        "logloss": round(log_loss(probs, actuals), 4),
        "by_league": by_league,
    }


def main() -> int:
    print("Chargement des données ...")
    df = fetch_and_clean()
    print(f"{len(df)} matchs disponibles.")

    print(f"Walk-forward {FIT_SEASON} (apprentissage des calibrateurs) ...")
    pooled_fit = walk_forward_pooled(df, FIT_SEASON)
    per_league_fit = walk_forward_per_league(df, FIT_SEASON)

    print(f"Walk-forward {EVAL_SEASON} (évaluation) ...")
    pooled_eval = walk_forward_pooled(df, EVAL_SEASON)
    per_league_eval = walk_forward_per_league(df, EVAL_SEASON)
    if not pooled_eval or not per_league_eval:
        print("Données d'évaluation insuffisantes.")
        return 1

    print("Ajustement des calibrateurs isotoniques ...")
    pooled_calibrator = Calibrated1X2.fit(
        [record["alpha"] for record in pooled_fit],
        [record["actual"] for record in pooled_fit],
    )
    calibrators_by_league: dict[str, Calibrated1X2] = {}
    for code in {record["league"] for record in per_league_fit}:
        subset = [record for record in per_league_fit if record["league"] == code]
        if subset:
            calibrators_by_league[code] = Calibrated1X2.fit(
                [record["alpha"] for record in subset],
                [record["actual"] for record in subset],
            )

    # --- Évaluation des variantes ---
    variants: dict[str, dict] = {}

    pooled_raw = np.asarray([record["raw"] for record in pooled_eval], dtype=float)
    pooled_alpha = np.asarray([record["alpha"] for record in pooled_eval], dtype=float)
    pooled_iso = pooled_calibrator.transform(pooled_alpha)

    per_league_alpha = np.asarray(
        [record["alpha"] for record in per_league_eval], dtype=float
    )
    per_league_iso = np.vstack([
        calibrators_by_league[record["league"]].transform_single(record["alpha"])
        if record["league"] in calibrators_by_league else record["alpha"]
        for record in per_league_eval
    ])

    variants["pooled_raw"] = summarize(pooled_eval, pooled_raw)
    variants["pooled_alpha"] = summarize(pooled_eval, pooled_alpha)
    variants["pooled_iso"] = summarize(pooled_eval, pooled_iso)
    variants["per_league_alpha"] = summarize(per_league_eval, per_league_alpha)
    variants["per_league_iso"] = summarize(per_league_eval, per_league_iso)

    # --- Affichage ---
    print()
    header = f"{'Variante':<22} {'Matchs':>7} {'Brier':>8} {'LogLoss':>9}"
    print(header)
    print("-" * len(header))
    for name, metrics in variants.items():
        print(
            f"{name:<22} {metrics['matches']:>7} "
            f"{metrics['brier']:>8.4f} {metrics['logloss']:>9.4f}"
        )

    print()
    leagues = sorted(variants["pooled_alpha"]["by_league"])
    print("Brier par championnat :")
    print(f"{'Ligue':<6}" + "".join(f"{name:>20}" for name in variants))
    for code in leagues:
        row = f"{code:<6}"
        for name in variants:
            value = variants[name]["by_league"].get(code, {}).get("brier")
            row += f"{value:>20.4f}" if value is not None else f"{'—':>20}"
        print(row)

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fit_season": FIT_SEASON,
        "eval_season": EVAL_SEASON,
        "variants": variants,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"\nRésultats enregistrés dans {OUT_PATH}")

    # Calibrateur de production : appris sur 2425 + 2526 (pooled), prêt à l'emploi
    production_fit = pooled_fit + pooled_eval
    production_calibrator = Calibrated1X2.fit(
        [record["alpha"] for record in production_fit],
        [record["actual"] for record in production_fit],
    )
    save(CALIBRATION_PATH, production_calibrator)
    print(f"Calibrateur de production (pooled, 2425+2526) : {CALIBRATION_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
