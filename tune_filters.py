"""
tune_filters.py - Sélection des filtres de value betting, sans snooping.

Démarche :
  1. Le backtesting a exporté TOUTES les cotes rencontrées (market_quotes.csv),
     avec pour chacune la probabilité du modèle, la cote et le résultat réel.
  2. On cherche les filtres (edge min/max, plage de cotes, marchés) qui maximisent
     le ROI sur la saison de VALIDATION (2526) avec un minimum de paris.
  3. On évalue ensuite ces filtres sur la saison de TEST hors échantillon (2627).

Le but est d'éviter de conclure sur un ROI flatteur obtenu en choisissant les
filtres sur les mêmes données (data snooping / overfitting de backtest).
"""

import json
import itertools
import os

import numpy as np
import pandas as pd

VALIDATION_SEASON = "2526"
HOLDOUT_SEASON = "2627"
MIN_BETS_VALIDATION = 150


def bootstrap_roi_ci(sel, n_boot=5000, seed=42):
    """
    Intervalle de confiance à 95 % du ROI par bootstrap (rééchantillonnage des paris).
    Retourne (borne_basse, borne_haute, probabilité_ROI_positif) en %.
    """
    if len(sel) < 5:
        return None, None, None
    rets = (sel["book_odds"] * sel["won"].astype(int) - 1.0).to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(rets), size=(n_boot, len(rets)))
    rois = rets[idx].mean(axis=1) * 100.0
    lo, hi = np.percentile(rois, [2.5, 97.5])
    return round(float(lo), 2), round(float(hi), 2), round(float((rois > 0).mean() * 100.0), 1)


def evaluate(df, min_edge, max_edge, min_odds, max_odds, markets):
    """Applique un jeu de filtres et retourne les statistiques de paris."""
    mask = (
        (df["edge_percent"] >= min_edge)
        & (df["edge_percent"] <= max_edge)
        & (df["book_odds"] >= min_odds)
        & (df["book_odds"] <= max_odds)
        & (df["market"].isin(markets))
    )
    sel = df[mask]
    n = len(sel)
    if n == 0:
        return {"bets": 0, "win_rate": 0.0, "profit": 0.0, "roi": 0.0}
    staked = n * 10.0
    returned = float((sel["book_odds"] * 10.0 * sel["won"].astype(int)).sum())
    return {
        "bets": n,
        "win_rate": round(float(sel["won"].mean()) * 100.0, 2),
        "profit": round(returned - staked, 2),
        "roi": round((returned - staked) / staked * 100.0, 2),
    }


def main():
    path = "data/market_quotes.csv"
    if not os.path.exists(path):
        raise SystemExit(
            "Lancez d'abord `python run_backtest.py` pour générer data/market_quotes.csv"
        )

    quotes = pd.read_csv(path)
    quotes["won"] = quotes["won"].astype(bool)
    quotes["season"] = quotes["season"].astype(str)

    validation = quotes[quotes["season"] == VALIDATION_SEASON]
    holdout = quotes[quotes["season"] == HOLDOUT_SEASON]

    print(f"Validation : {len(validation)} cotes ({VALIDATION_SEASON})")
    print(f"Test       : {len(holdout)} cotes ({HOLDOUT_SEASON})\n")

    market_sets = {
        "tous": ["Home", "Draw", "Away"],
        "1 et 2": ["Home", "Away"],
        "domicile": ["Home"],
        "extérieur": ["Away"],
        "nul": ["Draw"],
    }
    edge_grid = [(3, 1000), (5, 1000), (5, 20), (5, 15), (8, 15), (10, 20)]
    odds_grid = [(1.50, 5.00), (1.50, 4.00), (1.60, 3.50), (1.40, 6.00)]

    results = []
    for (label, markets), (min_edge, max_edge), (min_odds, max_odds) in itertools.product(
        market_sets.items(), edge_grid, odds_grid
    ):
        stats = evaluate(validation, min_edge, max_edge, min_odds, max_odds, markets)
        if stats["bets"] >= MIN_BETS_VALIDATION:
            results.append({
                "markets": label,
                "market_codes": markets,
                "min_edge": min_edge,
                "max_edge": max_edge,
                "min_odds": min_odds,
                "max_odds": max_odds,
                **stats,
            })

    if not results:
        raise SystemExit("Aucun jeu de filtres avec assez de paris en validation.")

    results.sort(key=lambda r: r["roi"], reverse=True)

    print("TOP 8 DES FILTRES SUR LA VALIDATION (2526) :")
    print(f"  {'Marchés':<10}{'Edge':>12}{'Cotes':>14}{'Paris':>8}{'ROI':>9}")
    for r in results[:8]:
        print(
            f"  {r['markets']:<10}{r['min_edge']:>5}-{r['max_edge']:<6}"
            f"{r['min_odds']:>6}-{r['max_odds']:<6}{r['bets']:>8}{r['roi']:>8}%"
        )

    best = results[0]
    print(f"\n>>> Filtres retenus (meilleur ROI validation) : {best['markets']}, "
          f"edge {best['min_edge']}–{best['max_edge']}%, "
          f"cotes {best['min_odds']}–{best['max_odds']}")

    print("\nAPPLICATION AUX TROIS SAISONS :")
    print(f"  {'Saison':<8}{'Rôle':<14}{'Paris':>8}{'Réussite':>10}{'ROI':>9}")
    report = {"selected_filters": {k: best[k] for k in (
        "markets", "min_edge", "max_edge", "min_odds", "max_odds")}, "by_season": {}}

    for season, role in (("2425", "référence"), (VALIDATION_SEASON, "validation"),
                         (HOLDOUT_SEASON, "test hors éch.")):
        subset = quotes[quotes["season"] == season]
        if subset.empty:
            continue
        stats = evaluate(
            subset, best["min_edge"], best["max_edge"],
            best["min_odds"], best["max_odds"], best["market_codes"],
        )
        report["by_season"][season] = {**stats, "role": role}
        print(f"  {season:<8}{role:<14}{stats['bets']:>8}{stats['win_rate']:>9}%"
              f"{stats['roi']:>8}%")

    os.makedirs("data", exist_ok=True)
    with open("data/filter_selection.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\n[FILTRES] Sélection sauvegardée : data/filter_selection.json")

    print("\nSIGNIFICATIVITÉ DU ROI (bootstrap 5000, IC 95 %) :")
    for season in ("2425", VALIDATION_SEASON, HOLDOUT_SEASON):
        subset = quotes[quotes["season"] == season]
        if subset.empty:
            continue
        mask = (
            (subset["edge_percent"] >= best["min_edge"])
            & (subset["edge_percent"] <= best["max_edge"])
            & (subset["book_odds"] >= best["min_odds"])
            & (subset["book_odds"] <= best["max_odds"])
            & (subset["market"].isin(best["market_codes"]))
        )
        sel = subset[mask]
        lo, hi, prob = bootstrap_roi_ci(sel)
        if lo is None:
            print(f"  {season} : trop peu de paris")
        else:
            report["by_season"][season].update({"roi_ci95": [lo, hi], "prob_roi_positif": prob})
            print(f"  {season} : {len(sel):>4} paris | ROI IC95 [ {lo:+.1f}% ; {hi:+.1f}% ] "
                  f"| P(ROI>0) = {prob}%")

    with open("data/filter_selection.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\nATTENTION : un ROI positif en validation peut être du bruit.")
    print("Un IC à 95 % qui contient 0 signifie qu'aucun avantage n'est démontré.")
    print("Seul le résultat hors échantillon (2627) a valeur de preuve.")


if __name__ == "__main__":
    main()
