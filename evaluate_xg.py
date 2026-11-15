"""
evaluate_xg.py - Compare les forces estimées sur les BUTS vs sur les xG.

Les xG ne sont disponibles que depuis la saison 2026-27 dans les fichiers
Football-Data (`HxG`, `AxG`). L'évaluation porte donc sur 2026-27 :

  - warm-up identique dans les deux cas (2024-25 + 2025-26, buts) ;
  - parcours chronologique de 2026-27, match par match, sans fuite ;
  - variante A : les forces attaque/défense utilisent les BUTS ;
  - variante B : elles utilisent les xG (les buts restent pour l'Elo et les
    fréquences de base).

Sortie : data/xg_comparison.json + tableau console.
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

from data_loader import fetch_and_clean  # noqa: E402
from prediction_engine import PredictionEngine  # noqa: E402

SEASON = "2627"
OUT_PATH = os.path.join("data", "xg_comparison.json")


def _actual(fthg, ftag) -> int:
    if fthg > ftag:
        return 0
    if fthg == ftag:
        return 1
    return 2


def walk_forward(df, season: str, use_xg: bool) -> list[dict]:
    target = df[df["Saison"] == season]
    if target.empty:
        return []

    ordered = df.sort_values("Date").reset_index(drop=True)
    date_series = ordered["Date"].dt.normalize()
    has_xg = "HxG" in ordered.columns and "AxG" in ordered.columns

    engine = PredictionEngine()
    engine.train(ordered, cutoff_date=target["Date"].min())

    records: list[dict] = []
    for day in sorted(target["Date"].dt.normalize().unique()):
        group = ordered[date_series == day]

        for row in group.itertuples(index=False):
            if row.Saison != season:
                continue
            raw = engine.predict_1x2_raw(row.HomeTeam, row.AwayTeam)
            alpha = engine._calibrate_1x2(*raw)
            records.append({
                "league": row.CodeChampionnat,
                "raw": raw,
                "alpha": alpha,
                "actual": _actual(int(row.FTHG), int(row.FTAG)),
            })

        for row in group.itertuples(index=False):
            xgh = getattr(row, "HxG", None) if (use_xg and has_xg) else None
            xga = getattr(row, "AxG", None) if (use_xg and has_xg) else None
            engine.update_match(
                row.HomeTeam,
                row.AwayTeam,
                int(row.FTHG),
                int(row.FTAG),
                row.Date,
                xgh=xgh,
                xga=xga,
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


def summarize(records: list[dict]) -> dict:
    probs = np.asarray([record["alpha"] for record in records], dtype=float)
    actuals = [record["actual"] for record in records]
    by_league: dict[str, dict] = {}
    for code in sorted({record["league"] for record in records}):
        indices = [i for i, record in enumerate(records) if record["league"] == code]
        by_league[code] = {
            "matches": len(indices),
            "brier": round(brier(probs[indices], [actuals[i] for i in indices]), 4),
            "logloss": round(log_loss(probs[indices], [actuals[i] for i in indices]), 4),
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
    if "HxG" not in df.columns:
        print("Colonnes xG absentes des données : impossible d'évaluer.")
        return 1

    print(f"Avertissement : xG disponibles uniquement pour {SEASON}.")
    print(f"Walk-forward {SEASON} — variante BUTS ...")
    goals = walk_forward(df, SEASON, use_xg=False)
    print(f"Walk-forward {SEASON} — variante xG ...")
    xg = walk_forward(df, SEASON, use_xg=True)

    if not goals or not xg:
        print("Données insuffisantes.")
        return 1

    summary_goals = summarize(goals)
    summary_xg = summarize(xg)

    print()
    header = f"{'Variante':<12} {'Matchs':>7} {'Brier':>8} {'LogLoss':>9}"
    print(header)
    print("-" * len(header))
    print(f"{'buts':<12} {summary_goals['matches']:>7} {summary_goals['brier']:>8.4f} {summary_goals['logloss']:>9.4f}")
    print(f"{'xG':<12} {summary_xg['matches']:>7} {summary_xg['brier']:>8.4f} {summary_xg['logloss']:>9.4f}")

    print()
    print("Brier par championnat :")
    print(f"{'Ligue':<6}{'buts':>10}{'xG':>10}")
    for code in sorted(summary_goals["by_league"]):
        print(
            f"{code:<6}"
            f"{summary_goals['by_league'][code]['brier']:>10.4f}"
            f"{summary_xg['by_league'].get(code, {}).get('brier', float('nan')):>10.4f}"
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": SEASON,
        "note": "xG disponibles uniquement à partir de 2026-27 (Football-Data HxG/AxG).",
        "goals": summary_goals,
        "xg": summary_xg,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"\nRésultats enregistrés dans {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
