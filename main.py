"""
main.py - Script de démonstration Phase 1

Pipeline :
  1. Télécharge les CSV des 3 dernières saisons des 5 championnats (Football-Data.co.uk).
  2. Nettoie et unifie les colonnes essentielles.
  3. Entraîne le moteur (Elo dynamique + forces attaque/défense avec Time Decay).
  4. Affiche une prédiction complète (1X2, Over/Under 2.5, Top 3 scores exacts,
     cotes justes) pour un match test.
  5. Détecte les Value Bets en comparant avec des cotes Bet365 de référence.
"""

from data_loader import fetch_and_clean
from prediction_engine import PredictionEngine


def find_available_team(engine, preferred):
    """
    Retourne l'équipe préférée si elle existe dans les données, sinon la première
    équipe disponible. Cela évite l'échec si le match test n'est pas dans le CSV.
    """
    if preferred in engine.teams:
        return preferred
    return next(iter(engine.teams)) if engine.teams else preferred


def main():
    print("=== FOOT PREDICT - Phase 1 : Prototype local ===\n")

    # 1. Téléchargement + nettoyage des données
    print("[1/4] Téléchargement des données Football-Data.co.uk ...")
    df = fetch_and_clean()

    # 2. Entraînement du moteur (Elo dynamique + Time Decay)
    print("[2/4] Entraînement du moteur mathématique ...")
    engine = PredictionEngine()
    engine.train(df)

    # Sauvegarde des Elo (optionnel, utile pour la Phase 2/3)
    engine.save_elo("models/elo_ratings.json")
    print(f"    {len(engine.teams)} équipes enregistrées. Elo sauvegardé dans models/elo_ratings.json")

    # 3. Prédiction pour un match test
    print("[3/4] Calcul de la prédiction ...")

    # Match test : Arsenal vs Liverpool (Premier League).
    # Si l'une des équipes est absente des données, on substitue une équipe présente.
    home_team = find_available_team(engine, "Arsenal")
    away_team = find_available_team(engine, "Liverpool")

    print(f"    Match : {home_team} vs {away_team}\n")

    prediction = engine.predict_match(home_team, away_team)
    engine.display_prediction(prediction)

    # 4. Détection de Value Bets (cotes Bet365 de référence à titre d'exemple)
    print("[4/4] Détection des Value Bets ...")
    # Cotes Bet365 indicatives (à remplacer par des cotes réelles au moment du pari)
    bookmaker_odds = {
        "Home": 2.20,
        "Draw": 3.40,
        "Away": 3.30,
        "Over 2.5": 1.80,
        "Under 2.5": 2.00,
    }

    value_bets = engine.detect_value_bets(home_team, away_team, bookmaker_odds)

    print("\n  COMPARAISON MODÈLE vs BET365 :")
    print(f"  {'Marché':<14} {'Cote modèle':<13} {'Cote B365':<12} {'Value':<10}")
    print("  " + "-" * 50)
    for vb in value_bets:
        flag = "  <-- VALUE BET" if vb["value_percent"] > 0 else ""
        print(
            f"  {vb['market']:<14} {vb['model_odds']:<13} {vb['book_odds']:<12} "
            f"{vb['value_percent']:+.2f}%{flag}"
        )

    best = value_bets[0] if value_bets else None
    if best and best["value_percent"] > 0:
        print(f"\n  >>> Meilleure Value Bet : {best['market']} à {best['book_odds']} "
              f"(+{best['value_percent']}% vs modèle){'   ← RECOMMANDÉ' if best['value_percent'] > 5 else ''}")
    else:
        print("\n  >>> Aucune Value Bet détectée (cotes bookmaker <= cotes justes du modèle).")

    print("\n=== Fin de la démonstration Phase 1 ===")


if __name__ == "__main__":
    main()
