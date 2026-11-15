"""
tune_model.py - Réglage des hyperparamètres du moteur (validation / test).

Principe :
  - La saison 2526 sert de VALIDATION pour choisir les hyperparamètres
    (Brier Score, qui est une scoring rule propre : moins sujet au sur-ajustement
    qu'un ROI).
  - La saison 2627 sert de TEST hors échantillon pour vérifier le gain.

Hyperparamètres testés :
  - CALIBRATION_ALPHA : force du mélange avec les fréquences de base
  - TIME_DECAY_LAMBDA : vitesse d'oubli de la forme ancienne (par jour)
  - ELO_GOAL_WEIGHT   : poids du différentiel Elo dans l'espérance de buts
"""

import itertools
import json
import os

import numpy as np

import prediction_engine as pe
from data_loader import fetch_and_clean
from backtest import compute_brier_score, compute_log_loss

VALIDATION = "2526"
HOLDOUT = "2627"


def evaluate(df, alpha, lam, elo_weight):
    """Walk-forward rapide : n'évalue que les saisons de validation et de test."""
    pe.CALIBRATION_ALPHA = alpha
    pe.TIME_DECAY_LAMBDA = lam
    pe.ELO_GOAL_WEIGHT = elo_weight

    engine = pe.PredictionEngine()
    scores = {VALIDATION: [], HOLDOUT: []}
    logloss = {VALIDATION: [], HOLDOUT: []}

    for _, row in df.iterrows():
        season = str(row["Saison"])
        fthg, ftag = float(row["FTHG"]), float(row["FTAG"])

        if season in (VALIDATION, HOLDOUT):
            engine.finalize_forces()
            try:
                pred = engine.predict_match(row["HomeTeam"], row["AwayTeam"])
                result = 1 if fthg > ftag else (-1 if fthg < ftag else 0)
                b = compute_brier_score(
                    pred["_prob_home_raw"], pred["_prob_draw_raw"],
                    pred["_prob_away_raw"], result,
                )
                scores[season].append(b)
                logloss[season].append(compute_log_loss(
                    pred["_prob_home_raw"], pred["_prob_draw_raw"],
                    pred["_prob_away_raw"], result,
                ))
            except Exception:
                pass

        engine.update_match(row["HomeTeam"], row["AwayTeam"], fthg, ftag, row["Date"])

    return {
        season: {
            "brier": round(float(np.mean(v)), 4) if v else None,
            "logloss": round(float(np.mean(logloss[season])), 4) if v else None,
            "n": len(v),
        }
        for season, v in scores.items()
    }


def main():
    print("Chargement des données...")
    df = fetch_and_clean()

    grid = list(itertools.product(
        [0.10, 0.25, 0.40],      # CALIBRATION_ALPHA
        [0.002, 0.008],          # TIME_DECAY_LAMBDA
        [0.30, 0.60],            # ELO_GOAL_WEIGHT
    ))

    results = []
    for alpha, lam, elo in grid:
        res = evaluate(df, alpha, lam, elo)
        results.append({
            "calibration_alpha": alpha,
            "time_decay_lambda": lam,
            "elo_goal_weight": elo,
            **res,
        })
        print(
            f"  alpha={alpha:<5} lambda={lam:<6} elo_w={elo:<5} "
            f"| val Brier={res[VALIDATION]['brier']} "
            f"| test Brier={res[HOLDOUT]['brier']}"
        )

    # Sélection sur la validation uniquement
    best = min(results, key=lambda r: r[VALIDATION]["brier"] or 9)
    print("\n>>> Meilleurs hyperparamètres (Brier validation) :")
    print(f"    alpha={best['calibration_alpha']}, "
          f"lambda={best['time_decay_lambda']}, elo_w={best['elo_goal_weight']}")
    print(f"    Validation 2526 : Brier {best[VALIDATION]['brier']}")
    print(f"    Test 2627       : Brier {best[HOLDOUT]['brier']}")

    os.makedirs("data", exist_ok=True)
    with open("data/model_tuning.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "best": best}, f, indent=2, ensure_ascii=False)
    print("\n[TUNING] Résultats sauvegardés : data/model_tuning.json")


if __name__ == "__main__":
    main()
