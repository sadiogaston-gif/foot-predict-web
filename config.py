"""
Configuration centrale du projet Foot Predict (Phase 1).
"""

# Championnats européens et leurs codes Football-Data.co.uk
# E0 = Premier League (Angleterre)
# F1 = Ligue 1 (France)
# D1 = Bundesliga (Allemagne)
# I1 = Serie A (Italie)
# SP1 = La Liga (Espagne)
LEAGUES = {
    "Premier League (Angleterre)": {"code": "E0", "country": "Angleterre"},
    "Championship (Angleterre)": {"code": "E1", "country": "Angleterre"},
    "Ligue 1 (France)": {"code": "F1", "country": "France"},
    "Ligue 2 (France)": {"code": "F2", "country": "France"},
    "Bundesliga (Allemagne)": {"code": "D1", "country": "Allemagne"},
    "2. Bundesliga (Allemagne)": {"code": "D2", "country": "Allemagne"},
    "Serie A (Italie)": {"code": "I1", "country": "Italie"},
    "Serie B (Italie)": {"code": "I2", "country": "Italie"},
    "La Liga (Espagne)": {"code": "SP1", "country": "Espagne"},
    "Segunda División (Espagne)": {"code": "SP2", "country": "Espagne"},
    "Primeira Liga (Portugal)": {"code": "P1", "country": "Portugal"},
    "Liga Portugal 2 (Portugal)": {"code": "P2", "country": "Portugal"},
    "Eredivisie (Pays-Bas)": {"code": "N1", "country": "Pays-Bas"},
    "Jupiler Pro League (Belgique)": {"code": "B1", "country": "Belgique"},
    "Süper Lig (Turquie)": {"code": "T1", "country": "Turquie"},
    "Scottish Premiership (Écosse)": {"code": "SC0", "country": "Écosse"},
    "Super League (Grèce)": {"code": "G1", "country": "Grèce"},
    "1. Lig (Turquie)": {"code": "T2", "country": "Turquie"},
}

# Codage des saisons au format YYZZ (ex: 2024-2025 -> "2425")
SEASONS = ["2425", "2526", "2627"]  # 3 dernières saisons

# URL de base des fichiers CSV sur Football-Data.co.uk
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"

# Colonnes essentielles à conserver
ESSENTIAL_COLUMNS = [
    "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG",
    "B365H", "B365D", "B365A",
]

# Colonnes de cotes optionnelles : moyennes du marché (utilisées en repli si
# Bet365 est absent d'un fichier). Elles sont conservées quand elles existent.
# HxG/AxG : Expected Goals domicile/extérieur (disponibles depuis 2026-27).
OPTIONAL_COLUMNS = ["AvgH", "AvgD", "AvgA", "HxG", "AxG"]

# Utiliser les xG (au lieu des buts) pour estimer les forces attaque/défense.
# Les buts restent utilisés pour l'Elo et les fréquences de base.
USE_XG = True

# Paramètres du moteur mathématique
ELO_BASE = 1500
ELO_K_FACTOR = 30
ELO_HOME_ADVANTAGE = 65  # points d'avantage terrain ajoutés à l'équipe domicile
TIME_DECAY_LAMBDA = 0.002  # décroissance exponentielle (par jour)
MAX_GOALS = 6  # matrice Poisson 0-6 x 0-6
DIXON_COLES_RHO = -0.10  # correction scores faibles (0-0, 1-0, 0-1, 1-1)

# Pont Elo -> espérance de buts.
# L'écart Elo devient un facteur multiplicatif exp(ELO_GOAL_WEIGHT * delta / 400),
# borné à +/- ELO_LOG_ADJUST_CLAMP en log (~1.42x / 0.70x) pour éviter l'emballement.
# 0.30 est le réglage retenu par validation (2526) : au-delà, le Brier se dégrade.
ELO_GOAL_WEIGHT = 0.30
ELO_LOG_ADJUST_CLAMP = 0.35

# Bornes de sécurité sur les espérances de buts
LAMBDA_MIN = 0.20
LAMBDA_MAX = 3.20

# Calibration : mélange (1 - alpha) * modèle + alpha * fréquences de base.
# Corrige la sur-confiance du modèle (indispensable pour un Brier Score honnête).
CALIBRATION_ALPHA = 0.25

# Priors avant tout match observé (empêchent les probabilités aberrantes en début d'historique)
PRIOR_MATCHES = 12
PRIOR_HOME_WIN = 0.45
PRIOR_DRAW = 0.26
PRIOR_AWAY_WIN = 0.29
PRIOR_AVG_HOME_GOALS = 1.55
PRIOR_AVG_AWAY_GOALS = 1.25
PRIOR_OVER_25 = 0.52

# Seuils de value bet par défaut
VALUE_THRESHOLD = 5.0  # en %
DEFAULT_STAKE = 10.0

# Filtres de mise (validés par l'analyse du backtest)
# - cotes extrêmes = longs shots où le modèle se trompe le plus
# - edges extrêmes = désaccords aberrants avec le marché, pas des valeurs réelles
BET_MIN_ODDS = 1.50
BET_MAX_ODDS = 5.00
BET_MAX_EDGE = 20.0   # en %
BET_MIN_PROB = 0.10   # probabilité modèle minimale

# ---------------------------------------------------------------------------
# Phase 2 - Backtesting (cahier des charges)
# ---------------------------------------------------------------------------
# Saison cible par défaut : 2025-2026 (dernière saison complète disponible).
BACKTEST_TARGET_SEASON = "2526"

# Seuil d'Expected Value : EV = (probabilité modèle * cote) - 1.
BACKTEST_EV_THRESHOLD = 0.05

# Plage de cotes autorisée pour un pari simulé (exclut les extrêmes).
BACKTEST_MIN_ODDS = 1.40
BACKTEST_MAX_ODDS = 5.00

# Gestion de mise.
BACKTEST_INITIAL_BANKROLL = 100.0
BACKTEST_KELLY_FRACTION = 0.25       # Quarter-Kelly
BACKTEST_KELLY_CAP = 0.03            # plafond : 3 % de la bankroll initiale

# ---------------------------------------------------------------------------
# Phase 5 - Améliorations mesurées (walk-forward 2024-25 -> 2025-26)
# ---------------------------------------------------------------------------
# Un moteur par championnat (au lieu d'un modèle unique sur 5 ligues).
# Brier mesuré : 0,6005 (par ligue) contre 0,6019 (pooled), à réglages égaux.
USE_PER_LEAGUE_ENGINES = True

# Calibration isotonique (apprise sur 2024-25, évaluée sur 2025-26).
# Mesurée neutre sur le modèle pooled (0,6012 vs 0,6019) et NÉFASTE combinée au
# modèle par ligue (0,6051) : désactivée par défaut. Mettre True pour l'utiliser.
CALIBRATION_ENABLED = False
CALIBRATION_FILE = "models/calibration.json"
