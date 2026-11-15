"""
prediction_engine.py - Moteur mathématique de prédiction football

Implémente :
  1. Classement Elo dynamique (base 1500, mise à jour après chaque match,
     résultat + écart de buts + avantage terrain).
  2. Forces attaque/défense avec pondération temporelle (Time Decay exponentiel).
  3. Loi de Poisson ajustée (Dixon-Coles simplifiée) sur une matrice 0-6 x 0-6,
     avec correction sur les scores faibles (0-0, 1-0, 0-1, 1-1).

Le moteur supporte l'entraînement par lots (train()) avec date limite
(cutoff_date) ET la mise à jour incrémentale match par match (update_match()),
indispensable pour le backtesting walk-forward sans fuite de données (Phase 2).

Optimisations Phase 2 :
  - les forces attaque/défense sont calculées à la volée (pas besoin de
    finalize_forces() après chaque match) ;
  - la matrice Poisson est construite par produit extérieur de deux vecteurs,
    ce qui divise par ~50 le nombre d'appels à scipy ;
  - predict_1x2() ne calcule que le strict nécessaire pour le backtesting.
"""

import json
import math
import os

import numpy as np
import pandas as pd
from scipy.stats import poisson

from config import (
    ELO_BASE,
    ELO_K_FACTOR,
    ELO_HOME_ADVANTAGE,
    ELO_GOAL_WEIGHT,
    ELO_LOG_ADJUST_CLAMP,
    TIME_DECAY_LAMBDA,
    MAX_GOALS,
    DIXON_COLES_RHO,
    LAMBDA_MIN,
    LAMBDA_MAX,
    CALIBRATION_ALPHA,
    PRIOR_MATCHES,
    PRIOR_HOME_WIN,
    PRIOR_DRAW,
    PRIOR_AWAY_WIN,
    PRIOR_AVG_HOME_GOALS,
    PRIOR_AVG_AWAY_GOALS,
    PRIOR_OVER_25,
    USE_XG,
)


def _expected_score(elo_a, elo_b):
    """Probabilité attendue qu'équipe A gagne contre équipe B (formule Elo classique)."""
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def _goal_margin_multiplier(goal_diff):
    """
    Multiplicateur de l'écart de buts pour la mise à jour Elo.
    Un match gagné d'un large écart fait monter/descendre davantage l'Elo.
    """
    return math.log(abs(goal_diff) + 1) * 2.2


class PredictionEngine:
    def __init__(self, teams=None):
        """
        Args:
            teams: liste optionnelle des équipes connues. Si None, initialisée vide
                   et peuplée dynamiquement au fil des matchs.
        """
        self.elo_ratings = {}          # nom equipe -> score Elo courant
        # Sommes pondérées pour forces attaque/défense (Time Decay)
        self.attack_sum = {}
        self.attack_weight_sum = {}
        self.defense_sum = {}
        self.defense_weight_sum = {}
        self.attack = {}               # force attaque finale (après finalize_forces)
        self.defense = {}              # force défense finale (après finalize_forces)

        self.trained = False           # True après finalize_forces()
        self.teams = set(teams) if teams else set()
        # Historique des Elo : equipe -> [(date, elo_apres_match), ...]
        # Utilisé par l'API (Phase 3) pour tracer la courbe d'évolution d'une équipe.
        self.elo_history = {}
        # Calibrateur optionnel (isotonic) appliqué aux probabilités 1X2
        self.calibrator = None
        self._reset_stats()

    # ------------------------------------------------------------------
    # Statistiques de base (fréquences 1X2, moyennes de buts)
    # ------------------------------------------------------------------
    def _reset_stats(self):
        """Réinitialise les compteurs de fréquences de base (1X2, Over 2.5, buts)."""
        self._n_matches = 0
        self._n_home_win = 0
        self._n_draw = 0
        self._n_away_win = 0
        self._n_over_25 = 0
        self._sum_home_goals = 0.0
        self._sum_away_goals = 0.0
        self._league_avg_home = PRIOR_AVG_HOME_GOALS
        self._league_avg_away = PRIOR_AVG_AWAY_GOALS
        self._last_date = None  # dernière date traitée (pivot du Time Decay)

    def _update_stats(self, fthg, ftag):
        """
        Met à jour les fréquences de base et les moyennes de buts APRÈS un match.
        Ces statistiques servent de référence de calibration pour les matchs suivants.
        """
        self._n_matches += 1
        self._sum_home_goals += fthg
        self._sum_away_goals += ftag

        n = self._n_matches + PRIOR_MATCHES
        self._league_avg_home = (self._sum_home_goals + PRIOR_MATCHES * PRIOR_AVG_HOME_GOALS) / n
        self._league_avg_away = (self._sum_away_goals + PRIOR_MATCHES * PRIOR_AVG_AWAY_GOALS) / n

        if fthg > ftag:
            self._n_home_win += 1
        elif fthg == ftag:
            self._n_draw += 1
        else:
            self._n_away_win += 1

        if fthg + ftag > 2.5:
            self._n_over_25 += 1

    def base_probs(self):
        """
        Fréquences de base (avec priors) : (p_home, p_draw, p_away, p_over_2_5).
        Sert de cible de calibration et de benchmark dans le backtesting.
        """
        n = self._n_matches + PRIOR_MATCHES
        p_home = (self._n_home_win + PRIOR_MATCHES * PRIOR_HOME_WIN) / n
        p_draw = (self._n_draw + PRIOR_MATCHES * PRIOR_DRAW) / n
        p_away = (self._n_away_win + PRIOR_MATCHES * PRIOR_AWAY_WIN) / n
        s = p_home + p_draw + p_away
        p_home, p_draw, p_away = p_home / s, p_draw / s, p_away / s
        p_over = (self._n_over_25 + PRIOR_MATCHES * PRIOR_OVER_25) / n
        return p_home, p_draw, p_away, p_over

    # ------------------------------------------------------------------
    # État des équipes / forces
    # ------------------------------------------------------------------
    def _init_team(self, team):
        if team not in self.elo_ratings:
            self.elo_ratings[team] = ELO_BASE
            self.attack_sum[team] = 0.0
            self.attack_weight_sum[team] = 0.0
            self.defense_sum[team] = 0.0
            self.defense_weight_sum[team] = 0.0
            self.attack[team] = 1.0
            self.defense[team] = 1.0
            self.elo_history[team] = []
            self.teams.add(team)

    def _apply_decay(self, now):
        """
        Applique la décroissance exponentielle aux sommes accumulées depuis le
        dernier match traité. C'est l'implémentation en ligne correcte du
        Time Decay : les observations anciennes pèsent exp(-lambda * jours).
        """
        if self._last_date is None:
            self._last_date = now
            return
        days = (now - self._last_date).days
        if days > 0:
            factor = math.exp(-TIME_DECAY_LAMBDA * days)
            if factor < 1.0:
                for t in self.teams:
                    self.attack_sum[t] *= factor
                    self.defense_sum[t] *= factor
                    self.attack_weight_sum[t] *= factor
                    self.defense_weight_sum[t] *= factor
        self._last_date = now

    def _add_match_forces(self, home_team, away_team, force_home, force_away):
        """
        Accumule les forces attaque/défense d'un match (poids 1).

        `force_home` / `force_away` valent les xG si disponibles (et si
        config.USE_XG), sinon les buts. La décroissance temporelle est appliquée
        globalement par _apply_decay() avant chaque nouveau match.
        """
        home_attack_raw = force_home / self._league_avg_home if self._league_avg_home > 0 else 1.0
        home_defense_raw = force_away / self._league_avg_away if self._league_avg_away > 0 else 1.0
        away_attack_raw = force_away / self._league_avg_away if self._league_avg_away > 0 else 1.0
        away_defense_raw = force_home / self._league_avg_home if self._league_avg_home > 0 else 1.0

        self.attack_sum[home_team] += home_attack_raw
        self.defense_sum[home_team] += home_defense_raw
        self.attack_weight_sum[home_team] += 1.0
        self.defense_weight_sum[home_team] += 1.0

        self.attack_sum[away_team] += away_attack_raw
        self.defense_sum[away_team] += away_defense_raw
        self.attack_weight_sum[away_team] += 1.0
        self.defense_weight_sum[away_team] += 1.0

    def _update_elo(self, home_team, away_team, fthg, ftag):
        """Met à jour les Elo après un match."""
        elo_home = self.elo_ratings[home_team] + ELO_HOME_ADVANTAGE
        elo_away = self.elo_ratings[away_team]

        p_home = _expected_score(elo_home, elo_away)
        p_away = 1.0 - p_home

        if fthg > ftag:
            res_home, res_away = 1.0, 0.0
        elif fthg < ftag:
            res_home, res_away = 0.0, 1.0
        else:
            res_home, res_away = 0.5, 0.5

        goal_diff = abs(fthg - ftag)
        margin_mult = _goal_margin_multiplier(goal_diff)

        self.elo_ratings[home_team] += ELO_K_FACTOR * margin_mult * (res_home - p_home)
        self.elo_ratings[away_team] += ELO_K_FACTOR * margin_mult * (res_away - p_away)

    @staticmethod
    def _force_values(fthg, ftag, xgh, xga):
        """
        Valeurs utilisées pour estimer les forces attaque/défense.

        Les xG sont préférés aux buts lorsqu'ils sont disponibles et que
        config.USE_XG est actif : ils mesurent la qualité des occasions et sont
        bien moins bruités qu'un score.
        """
        if USE_XG and xgh is not None and xga is not None:
            try:
                home_xg = float(xgh)
                away_xg = float(xga)
            except (TypeError, ValueError):
                return fthg, ftag
            if not (math.isnan(home_xg) or math.isnan(away_xg)):
                return home_xg, away_xg
        return fthg, ftag

    def update_match(
        self,
        home_team,
        away_team,
        fthg,
        ftag,
        match_date,
        now=None,
        xgh=None,
        xga=None,
    ):
        """
        Met à jour le moteur avec un seul match (incrémental).
        Utilisé par le backtesting walk-forward.

        Args:
            home_team, away_team: noms des équipes
            fthg, ftag: buts marqués (pour l'Elo et les fréquences de base)
            match_date: datetime du match
            now: conservé pour compatibilité, non utilisé (la décroissance est
                 appliquée par rapport à match_date).
            xgh, xga: Expected Goals domicile/extérieur (facultatif). Utilisés
                 pour les forces attaque/défense si disponibles.
        """
        self._init_team(home_team)
        self._init_team(away_team)

        # 0. Décroissance temporelle des sommes accumulées jusqu'à ce match
        self._apply_decay(match_date)

        # 1. Statistiques de base (fréquences 1X2 / Over 2.5 / moyennes de buts)
        self._update_stats(fthg, ftag)

        # 2. Mise à jour Elo (basée sur les cotes AVANT ce match)
        self._update_elo(home_team, away_team, fthg, ftag)

        # 2 bis. Historique Elo (sert aux graphiques de la Phase 3)
        self.elo_history.setdefault(home_team, []).append(
            (match_date, self.elo_ratings[home_team])
        )
        self.elo_history.setdefault(away_team, []).append(
            (match_date, self.elo_ratings[away_team])
        )

        # 3. Accumulation des forces (xG si disponibles, sinon buts)
        force_home, force_away = self._force_values(fthg, ftag, xgh, xga)
        self._add_match_forces(home_team, away_team, force_home, force_away)

    def _force(self, sums, weights, team):
        w = weights.get(team, 0.0)
        return (sums[team] / w) if w > 0 else 1.0

    def _attack_force(self, team):
        return self._force(self.attack_sum, self.attack_weight_sum, team)

    def _defense_force(self, team):
        return self._force(self.defense_sum, self.defense_weight_sum, team)

    def team_strengths(self, team):
        """
        Indices d'attaque et de défense d'une équipe (1.0 = moyenne du championnat).

        Exposé publiquement pour l'API (Phase 3) et les exports.
        Une défense > 1 signifie que l'équipe encaisse plus que la moyenne.
        """
        return self._attack_force(team), self._defense_force(team)

    def finalize_forces(self):
        """
        Calcule les forces attaque/défense finales (moyenne pondérée) à partir
        des sommes accumulées. Conservé pour l'affichage/les exports ; les
        prédictions utilisent directement les sommes (calcul à la volée).
        """
        for t in self.teams:
            self.attack[t] = self._attack_force(t)
            self.defense[t] = self._defense_force(t)
        self.trained = True

    # ------------------------------------------------------------------
    # Entraînement
    # ------------------------------------------------------------------
    def train(self, df, cutoff_date=None):
        """
        Entraînement chronologique sur un DataFrame trié par date.

        Args:
            df: DataFrame nettoyé (Date, HomeTeam, AwayTeam, FTHG, FTAG).
            cutoff_date: date limite optionnelle (exclusive). Seuls les matchs
                         STRICTEMENT antérieurs sont utilisés. Indispensable
                         pour le warm-up du backtesting (zéro fuite de données).

        Returns:
            self
        """
        if cutoff_date is not None:
            cutoff_date = pd.Timestamp(cutoff_date)
            df = df[df["Date"] < cutoff_date]

        df = df.sort_values("Date").reset_index(drop=True)

        # Réinitialisation complète de l'état
        self.elo_ratings = {}
        self.attack_sum = {}
        self.attack_weight_sum = {}
        self.defense_sum = {}
        self.defense_weight_sum = {}
        self.attack = {}
        self.defense = {}
        self.teams = set()
        self.trained = False
        self.elo_history = {}
        self._reset_stats()

        if not df.empty:
            cols = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]
            has_xg = USE_XG and "HxG" in df.columns and "AxG" in df.columns
            if has_xg:
                cols += ["HxG", "AxG"]
            for values in df[cols].itertuples(index=False, name=None):
                match_date, home, away, fthg, ftag = values[:5]
                xgh = values[5] if has_xg else None
                xga = values[6] if has_xg else None
                self.update_match(
                    home,
                    away,
                    float(fthg),
                    float(ftag),
                    match_date,
                    xgh=xgh,
                    xga=xga,
                )

        self.finalize_forces()
        return self

    def train_until(self, df, cutoff_date):
        """Alias explicite : entraîne uniquement sur les matchs antérieurs à cutoff_date."""
        return self.train(df, cutoff_date=cutoff_date)

    def get_elo(self, team):
        return self.elo_ratings.get(team, ELO_BASE)

    # ------------------------------------------------------------------
    # Prédiction
    # ------------------------------------------------------------------
    def _lambdas(self, home_team, away_team):
        self._init_team(home_team)
        self._init_team(away_team)

        elo_home = self.get_elo(home_team) + ELO_HOME_ADVANTAGE
        elo_away = self.get_elo(away_team)

        # L'écart Elo est converti en facteur multiplicatif d'espérance de buts.
        # Il est volontairement modéré : attaque/défense et Elo décrivent en partie
        # la même information, une correction trop forte crée de la sur-confiance.
        log_adjust = ELO_GOAL_WEIGHT * (elo_home - elo_away) / 400.0
        log_adjust = max(-ELO_LOG_ADJUST_CLAMP, min(log_adjust, ELO_LOG_ADJUST_CLAMP))
        elo_factor_home = math.exp(log_adjust)
        elo_factor_away = math.exp(-log_adjust)

        lambda_home = (
            self._league_avg_home
            * self._attack_force(home_team)
            * self._defense_force(away_team)
            * elo_factor_home
        )
        lambda_away = (
            self._league_avg_away
            * self._attack_force(away_team)
            * self._defense_force(home_team)
            * elo_factor_away
        )

        lambda_home = max(LAMBDA_MIN, min(lambda_home, LAMBDA_MAX))
        lambda_away = max(LAMBDA_MIN, min(lambda_away, LAMBDA_MAX))
        return lambda_home, lambda_away

    def _score_matrix(self, lambda_home, lambda_away):
        """
        Matrice de probabilité Poisson 0-6 x 0-6 avec correction Dixon-Coles.
        Construction vectorisée : un appel à poisson.pmf par équipe (au lieu de 49).
        """
        goals = np.arange(MAX_GOALS + 1)
        pmf_home = poisson.pmf(goals, lambda_home)
        pmf_away = poisson.pmf(goals, lambda_away)
        matrix = np.outer(pmf_home, pmf_away)

        # Correction Dixon-Coles simplifiée (scores faibles sous-estimés)
        corrections = {
            (0, 0): 1 - DIXON_COLES_RHO,
            (1, 0): 1 + DIXON_COLES_RHO,
            (0, 1): 1 + DIXON_COLES_RHO,
            (1, 1): 1 - DIXON_COLES_RHO,
        }
        for (i, j), factor in corrections.items():
            matrix[i, j] *= factor

        total = matrix.sum()
        if total > 0:
            matrix /= total
        return matrix

    def _calibrate_1x2(self, prob_home, prob_draw, prob_away):
        """
        Calibration : mélange (1 - alpha) * modèle + alpha * fréquences de base.
        Corrige la sur-confiance d'un Poisson brut, pour un Brier honnête.
        """
        base_home, base_draw, base_away, _ = self.base_probs()
        alpha = CALIBRATION_ALPHA
        if alpha > 0:
            prob_home = (1 - alpha) * prob_home + alpha * base_home
            prob_draw = (1 - alpha) * prob_draw + alpha * base_draw
            prob_away = (1 - alpha) * prob_away + alpha * base_away

        s = prob_home + prob_draw + prob_away
        if s > 0:
            prob_home, prob_draw, prob_away = prob_home / s, prob_draw / s, prob_away / s
        return prob_home, prob_draw, prob_away

    def set_calibrator(self, calibrator):
        """Attache un calibrateur de probabilités 1X2 (objet avec transform_single)."""
        self.calibrator = calibrator
        return self

    def _apply_calibrator(self, probabilities):
        if self.calibrator is None:
            return probabilities
        return self.calibrator.transform_single(probabilities)

    def predict_1x2_raw(self, home_team, away_team):
        """
        Probabilités 1X2 BRUTES (avant calibration alpha et isotonique).

        Utilisé pour ajuster un calibrateur sans circularité.
        """
        if not self.trained:
            raise RuntimeError("Le moteur doit être entraîné (train()) avant une prédiction.")

        lambda_home, lambda_away = self._lambdas(home_team, away_team)
        matrix = self._score_matrix(lambda_home, lambda_away)

        prob_home = float(np.tril(matrix, -1).sum())
        prob_draw = float(np.trace(matrix))
        prob_away = float(np.triu(matrix, 1).sum())

        total = prob_home + prob_draw + prob_away
        if total > 0:
            prob_home, prob_draw, prob_away = prob_home / total, prob_draw / total, prob_away / total

        return prob_home, prob_draw, prob_away

    def predict_1x2(self, home_team, away_team):
        """
        Calcul allégé : uniquement les probabilités 1X2 calibrées.
        Utilisé par le backtesting (beaucoup plus rapide que predict_match).

        Returns:
            (prob_home, prob_draw, prob_away) en fractions [0, 1].
        """
        raw = self.predict_1x2_raw(home_team, away_team)
        calibrated = self._calibrate_1x2(*raw)
        return self._apply_calibrator(calibrated)

    def score_matrix(self, home_team, away_team):
        """
        Expose la matrice de probabilités des scores exacts (API Phase 3).

        Returns:
            (lambda_home, lambda_away, matrix) où matrix[i, j] est la
            probabilité du score i-j (i buts domicile, j buts extérieur).
            La matrice couvre 0..MAX_GOALS (0-0 à 6-6).
        """
        if not self.trained:
            raise RuntimeError("Le moteur doit être entraîné (train()) avant une prédiction.")
        lambda_home, lambda_away = self._lambdas(home_team, away_team)
        return lambda_home, lambda_away, self._score_matrix(lambda_home, lambda_away)

    def predict_match(self, home_team, away_team):
        """
        Calcule les probabilités complètes d'un match donné.

        Returns un dict contenant :
          - prob_home, prob_draw, prob_away : probabilités 1X2
          - prob_over_2_5, prob_under_2_5 : probabilités Over/Under 2.5
          - prob_btts_yes, prob_btts_no : probabilité But des deux équipes
          - top_scores : liste des 3 scores exacts les plus probables
          - fair_odds : cotes justes (1/proba) pour 1X2 et Over 2.5
          - lambda_home, lambda_away : espérances de buts
        """
        if not self.trained:
            raise RuntimeError("Le moteur doit être entraîné (train()) avant une prédiction.")

        lambda_home, lambda_away = self._lambdas(home_team, away_team)
        prob_matrix = self._score_matrix(lambda_home, lambda_away)

        # ---- Probabilités 1X2 ----
        prob_home = float(np.tril(prob_matrix, -1).sum())
        prob_draw = float(np.trace(prob_matrix))
        prob_away = float(np.triu(prob_matrix, 1).sum())

        s = prob_home + prob_draw + prob_away
        if s > 0:
            prob_home /= s
            prob_draw /= s
            prob_away /= s

        # ---- Over / Under 2.5 ----
        goals_total = np.add.outer(
            np.arange(MAX_GOALS + 1), np.arange(MAX_GOALS + 1)
        )
        prob_over_2_5 = float(prob_matrix[goals_total > 2.5].sum())
        prob_under_2_5 = float(prob_matrix[goals_total <= 2.5].sum())

        # ---- Calibration ----
        prob_home, prob_draw, prob_away = self._calibrate_1x2(
            prob_home, prob_draw, prob_away
        )
        prob_home, prob_draw, prob_away = self._apply_calibrator(
            (prob_home, prob_draw, prob_away)
        )
        base_home, base_draw, base_away, base_over = self.base_probs()
        alpha = CALIBRATION_ALPHA
        if alpha > 0:
            prob_over_2_5 = (1 - alpha) * prob_over_2_5 + alpha * base_over
            prob_under_2_5 = 1.0 - prob_over_2_5

        # ---- BTTS (calculé sur la matrice non calibrée) ----
        prob_btts_yes = float(prob_matrix[1:, 1:].sum())
        prob_btts_no = 1.0 - prob_btts_yes

        # ---- Top 3 scores exacts ----
        flat_scores = []
        for i in range(MAX_GOALS + 1):
            for j in range(MAX_GOALS + 1):
                flat_scores.append((prob_matrix[i, j], f"{i}-{j}"))
        flat_scores.sort(key=lambda x: x[0], reverse=True)
        top_scores = [
            {"score": score, "probability": round(p * 100, 2)}
            for p, score in flat_scores[:3]
        ]

        def _fair_odds(p):
            return round(1.0 / p, 2) if p > 0 else float("inf")

        fair_odds = {
            "Home": _fair_odds(prob_home),
            "Draw": _fair_odds(prob_draw),
            "Away": _fair_odds(prob_away),
            "Over 2.5": _fair_odds(prob_over_2_5),
            "Under 2.5": _fair_odds(prob_under_2_5),
        }

        return {
            "home_team": home_team,
            "away_team": away_team,
            "lambda_home": round(lambda_home, 3),
            "lambda_away": round(lambda_away, 3),
            "elo_home": round(self.get_elo(home_team), 1),
            "elo_away": round(self.get_elo(away_team), 1),
            "prob_home": round(prob_home * 100, 2),
            "prob_draw": round(prob_draw * 100, 2),
            "prob_away": round(prob_away * 100, 2),
            "prob_over_2_5": round(prob_over_2_5 * 100, 2),
            "prob_under_2_5": round(prob_under_2_5 * 100, 2),
            "prob_btts_yes": round(prob_btts_yes * 100, 2),
            "prob_btts_no": round(prob_btts_no * 100, 2),
            "top_scores": top_scores,
            "fair_odds": fair_odds,
            # Brutes pour métriques
            "_prob_home_raw": prob_home,
            "_prob_draw_raw": prob_draw,
            "_prob_away_raw": prob_away,
            "_prob_over_2_5_raw": prob_over_2_5,
        }

    def detect_value_bets(self, home_team, away_team, bookmaker_odds):
        """
        Détecte les Value Bets en comparant les cotes justes du modèle
        aux cotes du bookmaker.
        """
        prediction = self.predict_match(home_team, away_team)
        model_odds = prediction["fair_odds"]

        value_bets = []
        for market, book_odds in bookmaker_odds.items():
            if market not in model_odds:
                continue
            m_odds = model_odds[market]
            if m_odds == float("inf") or book_odds <= 0:
                continue
            value_percent = (book_odds / m_odds - 1.0) * 100.0
            value_bets.append({
                "market": market,
                "model_odds": m_odds,
                "book_odds": book_odds,
                "value_percent": round(value_percent, 2),
            })

        value_bets.sort(key=lambda x: x["value_percent"], reverse=True)
        return value_bets

    # ------------------------------------------------------------------
    # Persistance / affichage
    # ------------------------------------------------------------------
    def save_elo(self, path="models/elo_ratings.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.elo_ratings, f, indent=2, ensure_ascii=False)

    def load_elo(self, path="models/elo_ratings.json"):
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            self.elo_ratings = json.load(f)
        self.trained = True
        for t in self.elo_ratings:
            if t not in self.attack:
                self.attack[t] = 1.0
                self.defense[t] = 1.0
        return True

    def display_prediction(self, prediction):
        """Affiche une prédiction complète et formatée dans la console."""
        print("\n" + "=" * 60)
        print(f"  PRÉDICTION : {prediction['home_team']} vs {prediction['away_team']}")
        print("=" * 60)
        print(f"  Elo domicile : {prediction['elo_home']}   |   Elo extérieur : {prediction['elo_away']}")
        print(f"  Lambda domicile : {prediction['lambda_home']}   |   Lambda extérieur : {prediction['lambda_away']}")
        print("-" * 60)
        print("  PROBABILITÉS 1X2 :")
        print(f"    1 (Domicile) : {prediction['prob_home']}%   -> Cote juste : {prediction['fair_odds']['Home']}")
        print(f"    X (Nul)      : {prediction['prob_draw']}%   -> Cote juste : {prediction['fair_odds']['Draw']}")
        print(f"    2 (Extérieur): {prediction['prob_away']}%   -> Cote juste : {prediction['fair_odds']['Away']}")
        print("-" * 60)
        print("  OVER / UNDER 2.5 :")
        print(f"    Over 2.5  : {prediction['prob_over_2_5']}%   -> Cote juste : {prediction['fair_odds']['Over 2.5']}")
        print(f"    Under 2.5 : {prediction['prob_under_2_5']}%   -> Cote juste : {prediction['fair_odds']['Under 2.5']}")
        print("-" * 60)
        print("  BTTS (But des deux équipes) :")
        print(f"    Oui : {prediction['prob_btts_yes']}%   |   Non : {prediction['prob_btts_no']}%")
        print("-" * 60)
        print("  TOP 3 SCORES EXACTS :")
        for idx, item in enumerate(prediction["top_scores"], 1):
            print(f"    {idx}. {item['score']}  ({item['probability']}%)")
        print("=" * 60 + "\n")
