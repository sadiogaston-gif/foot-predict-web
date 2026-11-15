"""
run_backtest.py - Lancement du backtesting Phase 2

Usage :
    python run_backtest.py
    python run_backtest.py --season 2526 --ev 0.05 --min-odds 1.40 --max-odds 5.00
    python run_backtest.py --season 2425 --no-cache

La saison précédente sert automatiquement de warm-up. Seuls les matchs de la
saison cible sont pariés. Les résultats sont exportés dans :
    - data/backtest_results.csv   (historique complet des paris)
    - data/backtest_report.json   (métriques agrégées)
    - data/market_quotes.csv      (toutes les cotes rencontrées)
"""

import argparse

from data_loader import fetch_and_clean
from backtest import (
    run_backtest,
    print_backtest_summary,
    save_backtest_results,
    save_backtest_report,
    save_market_quotes,
)
from config import (
    BACKTEST_TARGET_SEASON,
    BACKTEST_EV_THRESHOLD,
    BACKTEST_MIN_ODDS,
    BACKTEST_MAX_ODDS,
    BACKTEST_INITIAL_BANKROLL,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backtesting chronologique du modèle Foot Predict (Phase 2)"
    )
    parser.add_argument(
        "--season", default=BACKTEST_TARGET_SEASON,
        help="Saison cible (ex. 2526). La/les saison(s) précédente(s) servent de warm-up.",
    )
    parser.add_argument(
        "--ev", type=float, default=BACKTEST_EV_THRESHOLD,
        help="Seuil d'Expected Value (0.05 = 5 %%).",
    )
    parser.add_argument(
        "--min-odds", type=float, default=BACKTEST_MIN_ODDS,
        help="Cote minimale autorisée.",
    )
    parser.add_argument(
        "--max-odds", type=float, default=BACKTEST_MAX_ODDS,
        help="Cote maximale autorisée.",
    )
    parser.add_argument(
        "--bankroll", type=float, default=BACKTEST_INITIAL_BANKROLL,
        help="Bankroll initiale (unités).",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Force le retéléchargement des CSV (ignore data/raw).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=== FOOT PREDICT - Phase 2 : Backtesting chronologique ===\n")

    print("[1/2] Chargement et nettoyage des données ...")
    df = fetch_and_clean(use_cache=not args.no_cache)
    print(f"    {len(df)} matchs disponibles.\n")

    print("[2/2] Simulation walk-forward (zéro fuite de données) ...")
    metrics, bets_detail, market_quotes = run_backtest(
        df,
        target_season=args.season,
        ev_threshold=args.ev,
        min_odds=args.min_odds,
        max_odds=args.max_odds,
        initial_bankroll=args.bankroll,
    )

    print_backtest_summary(metrics)

    save_backtest_results(bets_detail, "data/backtest_results.csv")
    save_market_quotes(market_quotes, "data/market_quotes.csv")
    save_backtest_report(metrics, bets_detail, "data/backtest_report.json")

    print("=== Fin du backtesting Phase 2 ===")


if __name__ == "__main__":
    main()
