"""
backtest.py - Backtesting chronologique Phase 2 (zéro fuite de données)

Cahier des charges :
  1. Simulation journée après journée. Pour prédire un match du 15/03, le moteur
     ne connaît que les matchs STRICTEMENT antérieurs. La saison précédente sert
     de warm-up complet pour initialiser Elo et forces.
  2. Value bet si EV = (probabilité modèle * cote bookmaker) - 1 > 0.05,
     avec une cote comprise entre 1.40 et 5.00.
  3. Deux stratégies de mise simulées en parallèle :
       - A : flat betting, 1 unité par pari ;
       - B : Quarter-Kelly, plafonné à 3 % de la bankroll initiale (100 unités).
  4. Métriques : Brier modèle vs Brier bookmaker, nombre de paris, taux de
     réussite, cote moyenne, profit, ROI, drawdown maximum, détails par
     championnat et par type de pari.
  5. Export complet dans data/backtest_results.csv.

Aucune information future n'intervient dans une prédiction.
"""

import json
import math
import os

import numpy as np
import pandas as pd

from prediction_engine import PredictionEngine
from config import (
    BACKTEST_TARGET_SEASON,
    BACKTEST_EV_THRESHOLD,
    BACKTEST_MIN_ODDS,
    BACKTEST_MAX_ODDS,
    BACKTEST_INITIAL_BANKROLL,
    BACKTEST_KELLY_FRACTION,
    BACKTEST_KELLY_CAP,
)

MARKETS = ("Home", "Draw", "Away")
MARKET_LABELS = {"Home": "Victoire domicile", "Draw": "Nul", "Away": "Victoire extérieur"}


# ---------------------------------------------------------------------------
# Métriques de qualité probabiliste
# ---------------------------------------------------------------------------
def compute_brier_score(prob_home, prob_draw, prob_away, result):
    """
    Brier Score 1X2 pour un match (0 = parfait, 2 = pire).
    result : 1 victoire domicile, 0 nul, -1 victoire extérieur.
    """
    if result == 1:
        y = np.array([1.0, 0.0, 0.0])
    elif result == 0:
        y = np.array([0.0, 1.0, 0.0])
    else:
        y = np.array([0.0, 0.0, 1.0])
    p = np.array([prob_home, prob_draw, prob_away], dtype=float)
    return float(np.sum((p - y) ** 2))


def compute_log_loss(prob_home, prob_draw, prob_away, result):
    """Log-loss 1X2 (plus sensible à la sur-confiance que le Brier)."""
    p = prob_home if result == 1 else (prob_draw if result == 0 else prob_away)
    return -math.log(max(p, 1e-12))


def demargined_probs(odds_home, odds_draw, odds_away):
    """
    Convertit des cotes 1X2 en probabilités implicites sans marge bookmaker.
    Retourne (p_home, p_draw, p_away) ou None si les cotes sont invalides.
    """
    try:
        inv = [1.0 / float(odds_home), 1.0 / float(odds_draw), 1.0 / float(odds_away)]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if any(x <= 0 or not math.isfinite(x) for x in inv):
        return None
    s = sum(inv)
    return tuple(x / s for x in inv)


# ---------------------------------------------------------------------------
# Lecture des cotes : Bet365 en priorité, moyennes du marché en repli
# ---------------------------------------------------------------------------
def _valid_odds(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(v) and v > 1.0:
        return v
    return None


def market_odds(row, market):
    """
    Cote de référence pour un marché 1X2 :
      - B365H/B365D/B365A si disponible ;
      - sinon AvgH/AvgD/AvgA (moyenne du marché).
    """
    suffix = {"Home": "H", "Draw": "D", "Away": "A"}[market]
    for prefix in ("B365", "Avg"):
        value = _valid_odds(row.get(f"{prefix}{suffix}"))
        if value is not None:
            return value
    return None


def all_market_odds(row):
    """Dictionnaire {marché: cote} pour les marchés disponibles."""
    return {m: market_odds(row, m) for m in MARKETS if market_odds(row, m) is not None}


# ---------------------------------------------------------------------------
# Drawdown et agrégats
# ---------------------------------------------------------------------------
def max_drawdown(equity):
    """
    Drawdown maximum d'une courbe de bankroll (plus grande baisse depuis un pic).

    Returns: (drawdown en unités, drawdown en % du pic au point de drawdown max).
    Le pourcentage est calculé au même point que le drawdown en unités, afin
    d'éviter des incohérences (ex. 106 u de baisse sur un pic de 100 u = 106 %).
    """
    if not equity:
        return 0.0, 0.0
    peak = equity[0]
    mdd_units = 0.0
    peak_at_mdd = peak
    for value in equity:
        peak = max(peak, value)
        dd = peak - value
        if dd > mdd_units:
            mdd_units = dd
            peak_at_mdd = peak
    mdd_pct = (mdd_units / peak_at_mdd * 100.0) if peak_at_mdd > 0 else 0.0
    return mdd_units, mdd_pct


def _new_group():
    return {
        "bets": 0,
        "wins": 0,
        "sum_odds": 0.0,
        "staked_flat": 0.0,
        "profit_flat": 0.0,
        "staked_kelly": 0.0,
        "profit_kelly": 0.0,
    }


def _add_to_group(group, odds, won, stake_flat, profit_flat, stake_kelly, profit_kelly):
    group["bets"] += 1
    group["wins"] += int(won)
    group["sum_odds"] += odds
    group["staked_flat"] += stake_flat
    group["profit_flat"] += profit_flat
    group["staked_kelly"] += stake_kelly
    group["profit_kelly"] += profit_kelly


def _finalize_group(group):
    n = group["bets"]
    return {
        "bets": n,
        "wins": group["wins"],
        "win_rate_percent": round(group["wins"] / n * 100.0, 2) if n else 0.0,
        "avg_odds": round(group["sum_odds"] / n, 3) if n else 0.0,
        "flat": {
            "staked": round(group["staked_flat"], 2),
            "profit": round(group["profit_flat"], 2),
            "roi_percent": round(group["profit_flat"] / group["staked_flat"] * 100.0, 2)
            if group["staked_flat"] > 0 else 0.0,
        },
        "kelly": {
            "staked": round(group["staked_kelly"], 2),
            "profit": round(group["profit_kelly"], 2),
            "roi_percent": round(group["profit_kelly"] / group["staked_kelly"] * 100.0, 2)
            if group["staked_kelly"] > 0 else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Backtest principal
# ---------------------------------------------------------------------------
def run_backtest(
    df,
    target_season=BACKTEST_TARGET_SEASON,
    warmup_seasons=None,
    ev_threshold=BACKTEST_EV_THRESHOLD,
    min_odds=BACKTEST_MIN_ODDS,
    max_odds=BACKTEST_MAX_ODDS,
    initial_bankroll=BACKTEST_INITIAL_BANKROLL,
    kelly_fraction=BACKTEST_KELLY_FRACTION,
    kelly_cap=BACKTEST_KELLY_CAP,
    verbose=True,
):
    """
    Backtesting walk-forward avec warm-up sur la (les) saison(s) précédente(s).

    Args:
        df: DataFrame nettoyé, colonnes Date/HomeTeam/AwayTeam/FTHG/FTAG/
            B365H|AvgH/.../Saison/Championnat.
        target_season: saison testée (ex. "2526"). Seuls ses matchs sont pariés.
        warmup_seasons: saisons d'échauffement. None = toutes celles avant la cible.
        ev_threshold: EV minimale (0.05 = 5 %).
        min_odds, max_odds: plage de cotes autorisée.
        initial_bankroll: bankroll de départ (100 unités).
        kelly_fraction: fraction de Kelly (0.25 = Quarter-Kelly).
        kelly_cap: plafond de mise en fraction de la bankroll initiale (0.03).

    Returns:
        (metrics, bets_detail, market_quotes)
    """
    df = df.copy()
    df["Saison"] = df["Saison"].astype(str)
    available_seasons = sorted(df["Saison"].unique())
    target_season = str(target_season)

    if target_season not in available_seasons:
        raise ValueError(
            f"Saison cible {target_season} absente des données. "
            f"Saisons disponibles : {available_seasons}"
        )

    if warmup_seasons is None:
        warmup_seasons = [s for s in available_seasons if s < target_season]
    warmup_seasons = [str(s) for s in warmup_seasons]

    warmup_df = df[df["Saison"].isin(warmup_seasons)].sort_values("Date").reset_index(drop=True)
    target_df = df[df["Saison"] == target_season].sort_values("Date").reset_index(drop=True)

    if verbose:
        print(f"[BACKTEST] Warm-up : saisons {warmup_seasons} ({len(warmup_df)} matchs)")
        print(f"[BACKTEST] Saison cible : {target_season} ({len(target_df)} matchs)")
        print(f"[BACKTEST] Filtres : EV > {ev_threshold * 100:.1f} %, "
              f"cotes {min_odds:.2f}-{max_odds:.2f}")

    # --- 1. Initialisation sur la saison d'échauffement (strictement antérieure)
    engine = PredictionEngine()
    engine.train(warmup_df)

    # --- 2. Simulation jour après jour sur la saison cible
    brier_model, brier_book, brier_base, logloss = [], [], [], []
    correct_1x2 = 0
    predictions = 0

    bets_detail = []
    market_quotes = []

    global_group = _new_group()
    by_league = {}
    by_market = {m: _new_group() for m in MARKETS}

    bankroll_flat = float(initial_bankroll)
    bankroll_kelly = float(initial_bankroll)
    equity_flat = [bankroll_flat]
    equity_kelly = [bankroll_kelly]
    max_cap = kelly_cap * initial_bankroll

    # Les mises à jour du moteur sont différées à la fin de chaque journée :
    # tous les matchs d'une même date sont prédits avec l'état "strictement avant".
    pending_updates = []
    previous_date = None

    for row in target_df.itertuples(index=False):
        row_dict = row._asdict()
        home_team = row_dict["HomeTeam"]
        away_team = row_dict["AwayTeam"]
        fthg = float(row_dict["FTHG"])
        ftag = float(row_dict["FTAG"])
        match_date = row_dict["Date"]
        league = row_dict.get("Championnat", "Inconnu")

        # Nouvelle journée : on applique les résultats de la journée précédente
        if previous_date is not None and match_date != previous_date:
            for update in pending_updates:
                engine.update_match(*update)
            pending_updates = []
        previous_date = match_date

        if fthg > ftag:
            result, winner = 1, "Home"
        elif fthg < ftag:
            result, winner = -1, "Away"
        else:
            result, winner = 0, "Draw"

        # --- PRÉDICTION (moteur n'ayant vu que le passé) ---
        p_home, p_draw, p_away = engine.predict_1x2(home_team, away_team)
        probs = {"Home": p_home, "Draw": p_draw, "Away": p_away}
        predictions += 1

        brier_model.append(compute_brier_score(p_home, p_draw, p_away, result))
        logloss.append(compute_log_loss(p_home, p_draw, p_away, result))
        bh, bd, ba, _ = engine.base_probs()
        brier_base.append(compute_brier_score(bh, bd, ba, result))

        if max(probs, key=probs.get) == winner:
            correct_1x2 += 1

        # Brier du marché (cotes dé-marginalisées)
        odds_map = all_market_odds(row_dict)
        if len(odds_map) == 3:
            book = demargined_probs(
                odds_map["Home"], odds_map["Draw"], odds_map["Away"]
            )
            if book is not None:
                brier_book.append(compute_brier_score(*book, result))

        # --- Détection des value bets (une sélection par match : le meilleur EV)
        candidates = []
        for market in MARKETS:
            odds = odds_map.get(market)
            if odds is None:
                continue
            model_p = probs[market]
            ev = model_p * odds - 1.0
            won = market == winner

            # Trace exhaustive pour analyse hors-ligne
            market_quotes.append({
                "date": str(pd.Timestamp(match_date).date()),
                "season": target_season,
                "league": league,
                "match": f"{home_team} vs {away_team}",
                "market": market,
                "model_prob": round(model_p * 100, 2),
                "fair_odds": round(1.0 / model_p, 2) if model_p > 0 else None,
                "book_odds": odds,
                "ev_percent": round(ev * 100, 2),
                # Alias historique conservé pour tune_filters.py
                "edge_percent": round(ev * 100, 2),
                "result": winner,
                "won": won,
            })

            if ev > ev_threshold and min_odds <= odds <= max_odds:
                candidates.append((ev, market, odds, model_p))

        if candidates:
            ev, market, odds, model_p = max(candidates, key=lambda x: x[0])
            won = market == winner
            profit_flat = (odds - 1.0) if won else -1.0

            # Quarter-Kelly : f* = EV / (cote - 1), plafonné à 3 % de la bankroll initiale
            kelly_full = ev / (odds - 1.0) if odds > 1.0 else 0.0
            stake_kelly = min(
                kelly_fraction * kelly_full * bankroll_kelly,
                max_cap,
                bankroll_kelly,
            )
            stake_kelly = max(stake_kelly, 0.0)
            profit_kelly = stake_kelly * (odds - 1.0) if won else -stake_kelly

            bankroll_flat += profit_flat
            bankroll_kelly += profit_kelly
            equity_flat.append(bankroll_flat)
            equity_kelly.append(bankroll_kelly)

            _add_to_group(global_group, odds, won, 1.0, profit_flat, stake_kelly, profit_kelly)
            _add_to_group(
                by_league.setdefault(league, _new_group()),
                odds, won, 1.0, profit_flat, stake_kelly, profit_kelly,
            )
            _add_to_group(
                by_market[market], odds, won, 1.0, profit_flat, stake_kelly, profit_kelly
            )

            bets_detail.append({
                "Date": str(pd.Timestamp(match_date).date()),
                "Season": target_season,
                "League": league,
                "Match": f"{home_team} vs {away_team}",
                "Bet": market,
                "ModelProb": round(model_p * 100, 2),
                "FairOdds": round(1.0 / model_p, 2) if model_p > 0 else None,
                "Odds": round(odds, 3),
                "EV": round(ev * 100, 2),
                "Result": winner,
                "Won": int(won),
                "Stake_Flat": 1.0,
                "Profit_Flat": round(profit_flat, 4),
                "Stake_Kelly": round(stake_kelly, 4),
                "Profit_Kelly": round(profit_kelly, 4),
                "Bankroll_Flat": round(bankroll_flat, 4),
                "Bankroll_Kelly": round(bankroll_kelly, 4),
            })

        # --- MISE À JOUR différée : ce résultat ne servira qu'aux journées suivantes
        pending_updates.append((home_team, away_team, fthg, ftag, match_date))

    # Dernière journée
    for update in pending_updates:
        engine.update_match(*update)

    # --- 3. Agrégation des métriques
    n_bets = global_group["bets"]
    avg_odds = round(global_group["sum_odds"] / n_bets, 3) if n_bets else 0.0
    win_rate = round(global_group["wins"] / n_bets * 100.0, 2) if n_bets else 0.0
    avg_ev = round(
        float(np.mean([b["EV"] for b in bets_detail])), 2
    ) if bets_detail else 0.0

    dd_flat_units, dd_flat_pct = max_drawdown(equity_flat)
    dd_kelly_units, dd_kelly_pct = max_drawdown(equity_kelly)

    flat_metrics = {
        "staked": round(global_group["staked_flat"], 2),
        "profit": round(global_group["profit_flat"], 2),
        "roi_percent": round(global_group["profit_flat"] / global_group["staked_flat"] * 100.0, 2)
        if global_group["staked_flat"] > 0 else 0.0,
        "max_drawdown_units": round(dd_flat_units, 2),
        "max_drawdown_percent": round(dd_flat_pct, 2),
        "final_bankroll": round(bankroll_flat, 2),
    }
    kelly_metrics = {
        "staked": round(global_group["staked_kelly"], 2),
        "profit": round(global_group["profit_kelly"], 2),
        "roi_percent": round(global_group["profit_kelly"] / global_group["staked_kelly"] * 100.0, 2)
        if global_group["staked_kelly"] > 0 else 0.0,
        "max_drawdown_units": round(dd_kelly_units, 2),
        "max_drawdown_percent": round(dd_kelly_pct, 2),
        "final_bankroll": round(bankroll_kelly, 2),
    }

    metrics = {
        "target_season": target_season,
        "warmup_seasons": warmup_seasons,
        "warmup_matches": len(warmup_df),
        "target_matches": len(target_df),
        "predictions": predictions,
        "accuracy_1x2_percent": round(correct_1x2 / predictions * 100.0, 2) if predictions else 0.0,
        "brier_model": round(float(np.mean(brier_model)), 4) if brier_model else 0.0,
        "brier_bookmaker": round(float(np.mean(brier_book)), 4) if brier_book else 0.0,
        "brier_baserate": round(float(np.mean(brier_base)), 4) if brier_base else 0.0,
        "logloss_model": round(float(np.mean(logloss)), 4) if logloss else 0.0,
        "bets": n_bets,
        "wins": global_group["wins"],
        "win_rate_percent": win_rate,
        "avg_odds": avg_odds,
        "avg_ev_percent": avg_ev,
        "strategy_flat": flat_metrics,
        "strategy_kelly": kelly_metrics,
        "by_league": {k: _finalize_group(g) for k, g in by_league.items()},
        "by_market": {k: _finalize_group(g) for k, g in by_market.items() if g["bets"] > 0},
        "params": {
            "ev_threshold": ev_threshold,
            "min_odds": min_odds,
            "max_odds": max_odds,
            "initial_bankroll": initial_bankroll,
            "kelly_fraction": kelly_fraction,
            "kelly_cap": kelly_cap,
        },
    }

    if verbose:
        print(f"[BACKTEST] Terminé : {predictions} prédictions, {n_bets} paris simulés.")

    return metrics, bets_detail, market_quotes


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
def save_backtest_results(bets_detail, path="data/backtest_results.csv"):
    """Sauvegarde l'historique complet des paris simulés (CSV)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame(bets_detail)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[BACKTEST] {len(df)} paris -> {path}")
    return path


def save_market_quotes(market_quotes, path="data/market_quotes.csv"):
    """Sauvegarde toutes les cotes rencontrées (analyse de filtres hors-ligne)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame(market_quotes)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[BACKTEST] {len(df)} cotes marché -> {path}")
    return path


def save_backtest_report(metrics, bets_detail, path="data/backtest_report.json"):
    """Sauvegarde le rapport complet (métriques + détail des paris) en JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "bets": bets_detail}, f, indent=2, ensure_ascii=False)
    print(f"[BACKTEST] Rapport sauvegardé : {path}")
    return path


# ---------------------------------------------------------------------------
# Rapport console
# ---------------------------------------------------------------------------
def print_backtest_summary(metrics):
    """Affiche un bilan détaillé du backtest."""
    flat = metrics["strategy_flat"]
    kelly = metrics["strategy_kelly"]
    params = metrics["params"]

    print("\n" + "=" * 78)
    print("  RÉSULTATS DU BACKTESTING - PHASE 2")
    print("=" * 78)
    print(f"  Saison cible            : {metrics['target_season']} "
          f"({metrics['target_matches']} matchs)")
    print(f"  Warm-up                 : {metrics['warmup_seasons']} "
          f"({metrics['warmup_matches']} matchs)")
    print(f"  Prédictions             : {metrics['predictions']}")
    print("-" * 78)
    print("  QUALITÉ PROBABILISTE (Brier : 0 = parfait, 0.667 = hasard uniforme)")
    print(f"    Modèle                : {metrics['brier_model']}")
    print(f"    Bookmaker (dé-marginé): {metrics['brier_bookmaker']}")
    print(f"    Fréquences de base    : {metrics['brier_baserate']}")
    print(f"    Log-loss modèle       : {metrics['logloss_model']}")
    print(f"    Précision 1X2         : {metrics['accuracy_1x2_percent']}%")
    print("-" * 78)
    print(f"  SÉLECTION : EV > {params['ev_threshold'] * 100:.1f} %, "
          f"cotes {params['min_odds']:.2f}-{params['max_odds']:.2f}")
    print(f"    Paris simulés         : {metrics['bets']}")
    print(f"    Taux de réussite      : {metrics['win_rate_percent']}%")
    print(f"    Cote moyenne jouée    : {metrics['avg_odds']}")
    print(f"    EV moyenne            : {metrics['avg_ev_percent']}%")
    print("-" * 78)
    print("  STRATÉGIES DE MISE")
    print(f"  {'Stratégie':<30}{'Misé':>10}{'Profit':>10}{'ROI':>9}{'Drawdown':>11}")
    print(f"  {'A - Flat 1 unité':<30}{flat['staked']:>10.1f}{flat['profit']:>10.1f}"
          f"{flat['roi_percent']:>8.1f}%{flat['max_drawdown_units']:>10.1f}u")
    print(f"  {'B - Quarter-Kelly (cap 3%)':<30}{kelly['staked']:>10.1f}{kelly['profit']:>10.1f}"
          f"{kelly['roi_percent']:>8.1f}%{kelly['max_drawdown_units']:>10.1f}u")
    print(f"  Bankroll finale : A = {flat['final_bankroll']} u | B = {kelly['final_bankroll']} u "
          f"(départ {params['initial_bankroll']:.0f} u)")
    print(f"  Drawdown max    : A = {flat['max_drawdown_percent']}% | "
          f"B = {kelly['max_drawdown_percent']}%")
    print("-" * 78)

    if metrics.get("by_league"):
        print("  DÉTAIL PAR CHAMPIONNAT (stratégie A / stratégie B)")
        print(f"  {'Championnat':<28}{'Paris':>7}{'Réuss.':>8}{'ROI A':>9}{'ROI B':>9}"
              f"{'Profit A':>10}{'Profit B':>10}")
        for league, s in sorted(metrics["by_league"].items()):
            print(f"  {league[:27]:<28}{s['bets']:>7}{s['win_rate_percent']:>7.1f}%"
                  f"{s['flat']['roi_percent']:>8.1f}%{s['kelly']['roi_percent']:>8.1f}%"
                  f"{s['flat']['profit']:>10.1f}{s['kelly']['profit']:>10.1f}")

    if metrics.get("by_market"):
        print("-" * 78)
        print("  DÉTAIL PAR TYPE DE PARI (stratégie A / stratégie B)")
        print(f"  {'Type de pari':<28}{'Paris':>7}{'Réuss.':>8}{'Cote moy.':>11}"
              f"{'ROI A':>9}{'ROI B':>9}")
        for market, s in metrics["by_market"].items():
            label = MARKET_LABELS.get(market, market)
            print(f"  {label:<28}{s['bets']:>7}{s['win_rate_percent']:>7.1f}%"
                  f"{s['avg_odds']:>11.2f}{s['flat']['roi_percent']:>8.1f}%"
                  f"{s['kelly']['roi_percent']:>8.1f}%")

    print("=" * 78)
    print("  Rappel : un ROI positif sur un seul backtest ne prouve rien.")
    print("  La référence de qualité reste le Brier Score face au marché.")
    print("=" * 78 + "\n")
