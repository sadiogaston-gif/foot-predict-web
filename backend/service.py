"""
backend/service.py - Couche métier de l'API (Phase 3)

Rôle : faire le pont entre le moteur mathématique (Phase 1) / le backtesting
(Phase 2) et les endpoints REST.

Responsabilités :
  - charger les données historiques (avec cache local) et entraîner le moteur
    une seule fois (singleton thread-safe) ;
  - télécharger et mettre en cache les prochaines affiches (fixtures.csv de
    Football-Data.co.uk) ;
  - servir les prédictions des affiches depuis le fichier cache
    data/upcoming_predictions.json (généré par backend/update_pipeline.py) avec
    repli automatique sur calcul à la volée si le fichier est absent ;
  - exposer des dictionnaires prêts à sérialiser en JSON (aucun type numpy
    ne doit sortir de ce module) ;
  - lire les exports du backtest pour la page « Transparence ».

Aucune logique de prédiction n'est réimplémentée ici : tout passe par
PredictionEngine, afin de garantir une seule source de vérité mathématique.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd

# --- Bootstrap : le dossier racine (config.py, prediction_engine.py) ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import (  # noqa: E402
    BET_MAX_ODDS,
    BET_MIN_ODDS,
    CALIBRATION_ENABLED,
    CALIBRATION_FILE,
    USE_PER_LEAGUE_ENGINES,
    USE_XG,
    VALUE_THRESHOLD,
)
from backend.logos import get_provider as get_logo_provider  # noqa: E402
from data_loader import fetch_and_clean  # noqa: E402
from prediction_engine import PredictionEngine  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")
MODELS_DIR = os.path.join(ROOT, "models")
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
FIXTURES_CACHE = os.path.join(DATA_DIR, "fixtures.csv")
BACKTEST_CSV = os.path.join(DATA_DIR, "backtest_results.csv")
BACKTEST_JSON = os.path.join(DATA_DIR, "backtest_report.json")
PREDICTIONS_CACHE = os.path.join(DATA_DIR, "upcoming_predictions.json")

FIXTURES_TTL_SECONDS = 30 * 60  # rafraîchissement des affiches : 30 minutes

# Métadonnées d'affichage pour les 5 championnats suivis.
LEAGUE_META = {
    "E0": {"code": "E0", "name": "Premier League", "country": "Angleterre"},
    "E1": {"code": "E1", "name": "Championship", "country": "Angleterre"},
    "F1": {"code": "F1", "name": "Ligue 1", "country": "France"},
    "F2": {"code": "F2", "name": "Ligue 2", "country": "France"},
    "D1": {"code": "D1", "name": "Bundesliga", "country": "Allemagne"},
    "D2": {"code": "D2", "name": "2. Bundesliga", "country": "Allemagne"},
    "I1": {"code": "I1", "name": "Serie A", "country": "Italie"},
    "I2": {"code": "I2", "name": "Serie B", "country": "Italie"},
    "SP1": {"code": "SP1", "name": "La Liga", "country": "Espagne"},
    "SP2": {"code": "SP2", "name": "Segunda División", "country": "Espagne"},
    "P1": {"code": "P1", "name": "Primeira Liga", "country": "Portugal"},
    "P2": {"code": "P2", "name": "Liga Portugal 2", "country": "Portugal"},
    "N1": {"code": "N1", "name": "Eredivisie", "country": "Pays-Bas"},
    "B1": {"code": "B1", "name": "Jupiler Pro League", "country": "Belgique"},
    "T1": {"code": "T1", "name": "Süper Lig", "country": "Turquie"},
    "SC0": {"code": "SC0", "name": "Scottish Premiership", "country": "Écosse"},
    "G1": {"code": "G1", "name": "Super League", "country": "Grèce"},
    "T2": {"code": "T2", "name": "1. Lig", "country": "Turquie"},
}

MARKET_LABELS = {
    "home": "Victoire domicile",
    "draw": "Match nul",
    "away": "Victoire extérieur",
    "over_2_5": "Over 2.5 buts",
    "under_2_5": "Under 2.5 buts",
}


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def _num(value):
    """Convertit une valeur CSV en float exploitable, sinon None."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 1.0:
        return None
    return v


def _clean_str(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _int_or_none(value):
    """Convertit une valeur en entier exploitable, sinon None."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _iso(value):
    """Sérialise une date pandas/python en chaîne ISO (ou None)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def _kickoff_iso(row: dict) -> str | None:
    """
    Construit le coup d'envoi au format ISO 8601 AVEC fuseau horaire.

    Priorité :
      1. `CommenceTimeUTC` (The Odds API) — instant exact en UTC ;
      2. `Date` + `Time` interprétés dans le fuseau d'affichage du pipeline
         (`DISPLAY_TIMEZONE`, Europe/Paris par défaut).

    Le suffixe explicite (`Z` ou `+01:00`/`+02:00`) permet au frontend de
    convertir vers l'heure locale du visiteur sans ambiguïté (hiver/été).
    """
    from zoneinfo import ZoneInfo  # import local : py3.9+ uniquement

    display_tz = ZoneInfo(os.environ.get("DISPLAY_TIMEZONE", "Europe/Paris"))

    # 1) Instant exact fourni par The Odds API
    raw_utc = row.get("CommenceTimeUTC")
    if raw_utc is not None and not (isinstance(raw_utc, float) and math.isnan(raw_utc)):
        text = str(raw_utc).strip()
        if text:
            try:
                if text.endswith("Z"):
                    dt = datetime.fromisoformat(text[:-1] + "+00:00")
                else:
                    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except (ValueError, TypeError):
                pass

    # 2) Repli : Date + Time dans le fuseau d'affichage
    date_value = row.get("Date")
    if date_value is None or (isinstance(date_value, float) and math.isnan(date_value)):
        return None
    try:
        day = pd.Timestamp(date_value)
    except (ValueError, TypeError):
        return None
    if pd.isna(day):
        return None
    time_txt = _clean_str(row.get("Time"))
    hour, minute = 0, 0
    if time_txt and ":" in time_txt:
        try:
            hour, minute = (int(part) for part in time_txt[:5].split(":")[:2])
        except (ValueError, TypeError):
            pass
    local = datetime(
        int(day.year), int(day.month), int(day.day), hour, minute, tzinfo=display_tz
    )
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def match_id_for(league_code, original_date, home_team, away_team):
    """
    Identifiant stable d'un match (utilisé dans /api/matches/{match_id}).

    Basé sur la date ORIGINELLE du calendrier (avant reprojection éventuelle),
    afin que l'URL reste valide d'un rafraîchissement à l'autre.
    """
    raw = f"{league_code}|{original_date}|{home_team}|{away_team}"
    return "m_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:11]


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------
class MatchService:
    """Singleton : un seul modèle entraîné par processus."""

    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._model_lock = threading.Lock()
        self._fixtures_lock = threading.Lock()
        self._backtest_lock = threading.Lock()

        self._df: pd.DataFrame | None = None
        self._engine: PredictionEngine | None = None
        self._engines: dict[str, PredictionEngine] = {}
        self._model_loaded_at: datetime | None = None

        self._fixtures: pd.DataFrame | None = None
        self._fixtures_meta: dict = {}
        self._fixtures_loaded_at: datetime | None = None
        self._predictions: dict[str, dict] = {}
        self._cached_predictions: dict[str, dict] = {}
        self._cached_predictions_payload_data: dict = {}
        self._cached_predictions_mtime: float | None = None

        self._backtest_cache: dict | None = None

    # ------------------------------------------------------------------
    # Modèle
    # ------------------------------------------------------------------
    def ensure_model(self) -> PredictionEngine:
        """Charge les données et entraîne le moteur (une seule fois)."""
        if self._engine is not None:
            return self._engine
        with self._model_lock:
            if self._engine is not None:
                return self._engine

            df = fetch_and_clean()
            if df is None or df.empty:
                raise RuntimeError(
                    "Aucune donnée historique exploitable. Vérifiez la connexion "
                    "réseau ou le cache data/raw."
                )

            engines, pooled = self.train_engines(df)

            self._df = df
            self._engine = pooled
            self._engines = engines
            self._model_loaded_at = datetime.now(timezone.utc)
        return self._engine

    def _load_calibrator(self):
        """Calibrateur isotonique optionnel (voir config.CALIBRATION_ENABLED)."""
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

    def train_engines(self, df):
        """
        Entraîne les moteurs de prédiction.

        Returns:
            (engines, pooled) où engines est un dict {code ligue: moteur} si
            USE_PER_LEAGUE_ENGINES, sinon un dict vide.
        """
        calibrator = self._load_calibrator()
        engines: dict[str, PredictionEngine] = {}

        if USE_PER_LEAGUE_ENGINES:
            for code in sorted(df["CodeChampionnat"].unique()):
                subset = df[df["CodeChampionnat"] == code]
                if subset.empty:
                    continue
                league_engine = PredictionEngine()
                league_engine.train(subset)
                if calibrator is not None:
                    league_engine.set_calibrator(calibrator)
                engines[code] = league_engine

        pooled = PredictionEngine()
        pooled.train(df)
        if calibrator is not None:
            pooled.set_calibrator(calibrator)
        return engines, pooled

    def engine_for(self, league_code: str) -> PredictionEngine:
        """Moteur à utiliser pour un championnat (par ligue si activé)."""
        self.ensure_model()
        code = (league_code or "").strip().upper()
        return self._engines.get(code) or self._engine

    @property
    def model_ready(self) -> bool:
        return self._engine is not None

    def model_info(self) -> dict:
        self.ensure_model()
        return {
            "teams": len(self._engine.teams),
            "matches": int(len(self._df)),
            "seasons": sorted(self._df["Saison"].unique().tolist()),
            "leagues": sorted(self._df["CodeChampionnat"].unique().tolist()),
            "loaded_at": self._model_loaded_at.isoformat() if self._model_loaded_at else None,
            "engine": "Elo dynamique + Time Decay + Poisson Dixon-Coles",
            "per_league": USE_PER_LEAGUE_ENGINES,
            "engines": len(self._engines),
            "calibration": CALIBRATION_ENABLED,
            "xg": USE_XG,
        }

    # ------------------------------------------------------------------
    # Affiches (fixtures)
    # ------------------------------------------------------------------
    def _download_fixtures(self) -> pd.DataFrame | None:
        """Télécharge fixtures.csv (cache disque en cas d'échec)."""
        try:
            import requests

            response = requests.get(
                FIXTURES_URL,
                timeout=20,
                headers={"User-Agent": "FootPredict/1.0 (+phase3)"},
            )
            response.raise_for_status()
            # football-data.co.uk n'annonce pas de charset : response.text serait
            # décodé en latin-1 et le BOM deviendrait « ï»¿Div ». On décode les
            # octets explicitement en UTF-8 (avec suppression du BOM).
            text = response.content.decode("utf-8-sig", errors="replace")
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(FIXTURES_CACHE, "w", encoding="utf-8") as handle:
                handle.write(text)
            return pd.read_csv(io.StringIO(text))
        except Exception as exc:  # réseau indisponible, format inattendu...
            print(f"[FIXTURES] Téléchargement impossible : {exc}")
            return self._read_cached_fixtures()

    def _read_cached_fixtures(self) -> pd.DataFrame | None:
        if not os.path.exists(FIXTURES_CACHE):
            return None
        try:
            return pd.read_csv(FIXTURES_CACHE, encoding="utf-8-sig")
        except Exception as exc:
            print(f"[FIXTURES] Cache illisible : {exc}")
            return None

    def _prepare_fixtures(self, raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
        """
        Normalise les affiches :
          - ne garde que les 5 championnats suivis ;
          - parse les dates / heures ;
          - reprojette la journée sur les semaines à venir si le fichier
            Football-Data ne contient plus de matchs futurs (snapshot figé).
        """
        if raw is None or raw.empty:
            return pd.DataFrame(), {
                "source": "empty",
                "projected": False,
                "note": "Aucune affiche disponible (fixtures.csv inaccessible).",
            }

        raw = raw.copy()
        raw.columns = [str(c).strip().lstrip("\ufeff") for c in raw.columns]

        required = {"Div", "Date", "HomeTeam", "AwayTeam"}
        if not required.issubset(raw.columns):
            return pd.DataFrame(), {
                "source": "invalid",
                "projected": False,
                "note": "fixtures.csv ne contient pas les colonnes attendues.",
            }

        df = raw[raw["Div"].astype(str).isin(LEAGUE_META.keys())].copy()
        if df.empty:
            return pd.DataFrame(), {
                "source": "empty",
                "projected": False,
                "note": "Aucune affiche des 5 grands championnats dans fixtures.csv.",
            }

        parsed = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
        if parsed.isna().all():
            parsed = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
        df["Date"] = parsed
        df = df.dropna(subset=["Date"])
        df["HomeTeam"] = df["HomeTeam"].map(_clean_str)
        df["AwayTeam"] = df["AwayTeam"].map(_clean_str)
        df = df[(df["HomeTeam"] != "") & (df["AwayTeam"] != "")]
        if "Time" not in df.columns:
            df["Time"] = ""

        # Date origine (pour un identifiant stable) avant toute reprojection
        df["OriginalDate"] = df["Date"].dt.strftime("%Y-%m-%d")

        today = pd.Timestamp(date.today()).normalize()
        first_date = df["Date"].min().normalize()

        # On ne conserve que les affiches à venir. Si le fichier est un snapshot
        # entièrement passé (le cas le plus fréquent hors journée en cours), on
        # reprojette la dernière journée connue d'un nombre ENTIER de semaines
        # pour conserver les jours de semaine (ven/sam/dim/lun).
        future = df[df["Date"] >= today]
        projected = False
        shift_days = 0

        if future.empty:
            weeks = math.ceil((today - first_date).days / 7)
            shift_days = 7 * max(1, weeks)
            df = df.copy()
            df["Date"] = df["Date"] + pd.Timedelta(days=shift_days)
            projected = True
        else:
            df = future.copy()

        df = df.sort_values(["Date", "Time"]).reset_index(drop=True)

        meta = {
            "source": "fixtures.csv",
            "projected": projected,
            "shift_days": shift_days,
            "original_first_date": str(first_date.date()),
            "note": (
                "fixtures.csv de Football-Data.co.uk ne contenait plus de matchs "
                "futurs (snapshot figé au {}). Les affiches de la dernière journée "
                "connue sont reprojetées de {} jours sur le calendrier à venir, "
                "à titre de démonstration.".format(first_date.date(), shift_days)
                if projected
                else "Affiches à venir issues de fixtures.csv."
            ),
        }
        return df, meta

    def _cache_is_fresh(self) -> bool:
        """Le fichier disque est-il plus récent que le TTL ?"""
        if not os.path.exists(FIXTURES_CACHE):
            return False
        return (time.time() - os.path.getmtime(FIXTURES_CACHE)) < FIXTURES_TTL_SECONDS

    def ensure_fixtures(self, force: bool = False) -> pd.DataFrame:
        """Charge les affiches (cache mémoire 30 min, puis disque frais, puis réseau)."""
        now = datetime.now(timezone.utc)
        with self._fixtures_lock:
            fresh = (
                self._fixtures is not None
                and self._fixtures_loaded_at is not None
                and (now - self._fixtures_loaded_at).total_seconds() < FIXTURES_TTL_SECONDS
            )
            if fresh and not force:
                return self._fixtures

            # Le cache disque n'est utilisé que s'il est récent ; sinon on tente
            # une mise à jour réseau (repli sur le cache en cas d'échec).
            raw = None
            if not force and self._cache_is_fresh():
                raw = self._read_cached_fixtures()
            if raw is None or raw.empty:
                raw = self._download_fixtures()
            if raw is None or raw.empty:
                raw = self._read_cached_fixtures()

            fixtures, meta = self._prepare_fixtures(raw)
            self._fixtures = fixtures
            self._fixtures_meta = meta
            self._fixtures_loaded_at = now
            self._predictions = {}
            return fixtures

    # ------------------------------------------------------------------
    # Prédictions mises en cache (fichier généré par backend/update_pipeline.py)
    # ------------------------------------------------------------------
    def _load_predictions_payload(self) -> dict:
        """
        Lit le fichier data/upcoming_predictions.json (généré par le pipeline
        d'automatisation backend/update_pipeline.py) et renvoie le payload complet
        (generated_at, meta, matches). {} si le fichier est absent ou illisible.
        """
        if not os.path.exists(PREDICTIONS_CACHE):
            return {}
        try:
            with open(PREDICTIONS_CACHE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return {}
        if isinstance(payload, list):  # ancien format : liste de matchs
            return {"matches": payload}
        return payload if isinstance(payload, dict) else {}

    def _cached_predictions_payload(self) -> dict:
        """Payload du cache disque, rechargé uniquement si le fichier a changé."""
        try:
            mtime = os.path.getmtime(PREDICTIONS_CACHE)
        except OSError:
            return {}
        if self._cached_predictions_mtime is None or mtime != self._cached_predictions_mtime:
            self._cached_predictions_mtime = mtime
            self._cached_predictions_payload_data = self._load_predictions_payload()
            matches = self._cached_predictions_payload_data.get("matches") or []
            self._cached_predictions = {
                entry["id"]: entry
                for entry in matches
                if isinstance(entry, dict) and entry.get("id")
            }
        return self._cached_predictions_payload_data

    def _cached_predictions_index(self) -> dict[str, dict]:
        """Index {match_id: prédiction} du fichier cache (généré par le pipeline)."""
        self._cached_predictions_payload()
        return self._cached_predictions

    def predictions_cache_info(self) -> dict:
        """
        État du cache de prédictions (exposé par /api/health pour diagnostiquer
        rapidement un cache absent, vide ou périmé).
        """
        payload = self._cached_predictions_payload()
        matches = payload.get("matches") or []
        meta = payload.get("meta") or {}
        return {
            "exists": os.path.exists(PREDICTIONS_CACHE),
            "count": len(matches),
            "generated_at": payload.get("generated_at"),
            "source": meta.get("source") or ("file-cache" if matches else None),
            "window": meta.get("window"),
        }

    # ------------------------------------------------------------------
    # Prédiction d'une affiche
    # ------------------------------------------------------------------
    def _predict_row(self, row: dict, engine: PredictionEngine | None = None) -> dict:
        engine = engine or self.ensure_model()
        home = _clean_str(row["HomeTeam"])
        away = _clean_str(row["AwayTeam"])
        league_code = _clean_str(row["Div"])
        meta = LEAGUE_META.get(league_code, {"name": league_code, "country": ""})

        prediction = engine.predict_match(home, away)

        # Attention : les colonnes « B365>2.5 » ne sont pas des identifiants
        # Python valides, d'où l'usage de dicts (to_dict) et non d'itertuples.
        odds = {
            "home": _num(row.get("B365H")) or _num(row.get("AvgH")),
            "draw": _num(row.get("B365D")) or _num(row.get("AvgD")),
            "away": _num(row.get("B365A")) or _num(row.get("AvgA")),
            "over_2_5": _num(row.get("B365>2.5")) or _num(row.get("Avg>2.5")),
            "under_2_5": _num(row.get("B365<2.5")) or _num(row.get("Avg<2.5")),
        }

        model_probs = {
            "home": float(prediction["_prob_home_raw"]),
            "draw": float(prediction["_prob_draw_raw"]),
            "away": float(prediction["_prob_away_raw"]),
            "over_2_5": float(prediction["_prob_over_2_5_raw"]),
            "under_2_5": 1.0 - float(prediction["_prob_over_2_5_raw"]),
        }

        fair = prediction["fair_odds"]

        def _safe_odds(value):
            """Les cotes infinies ne sont pas du JSON valide : on renvoie None."""
            if value is None:
                return None
            if isinstance(value, float) and not math.isfinite(value):
                return None
            return value

        fair_odds = {
            "home": _safe_odds(fair["Home"]),
            "draw": _safe_odds(fair["Draw"]),
            "away": _safe_odds(fair["Away"]),
            "over_2_5": _safe_odds(fair["Over 2.5"]),
            "under_2_5": _safe_odds(fair["Under 2.5"]),
        }

        # --- Value bets : EV = probabilité modèle * cote bookmaker - 1 ---
        # Règle Phase 2 : EV >= 5 % ET cote dans [1.40 ; 5.00]. La borne de cotes
        # écarte les longs shots, où le modèle se trompe le plus.
        value_bets = []
        for market, book_odds in odds.items():
            if book_odds is None:
                continue
            probability = model_probs[market]
            ev = probability * book_odds - 1.0
            value_bets.append({
                "market": market,
                "label": MARKET_LABELS[market],
                "model_probability": round(probability * 100, 2),
                "fair_odds": round(1.0 / probability, 2) if probability > 0 else None,
                "book_odds": round(book_odds, 3),
                "ev_percent": round(ev * 100, 2),
                "qualifies": bool(
                    ev * 100.0 >= VALUE_THRESHOLD
                    and BET_MIN_ODDS <= book_odds <= BET_MAX_ODDS
                ),
            })
        value_bets.sort(key=lambda item: item["ev_percent"], reverse=True)
        # Le badge « value bet » ne porte que sur le 1X2, comme les paris
        # simulés en Phase 2 (marchés Over/Under affichés à titre informatif).
        positives = [
            v for v in value_bets
            if v["qualifies"] and v["market"] in ("home", "draw", "away")
        ]

        # Coup d'envoi au format ISO avec fuseau (instant exact quand disponible).
        kickoff_iso = _kickoff_iso(row)
        kickoff = kickoff_iso

        return {
            "id": match_id_for(league_code, row["OriginalDate"], home, away),
            "league_code": league_code,
            "league": meta["name"],
            "league_long": f"{meta['name']} ({meta['country']})" if meta["country"] else meta["name"],
            "country": meta["country"],
            "date": _iso(row["Date"]),
            "time": _clean_str(row.get("Time")),
            "kickoff": kickoff,
            "kickoff_utc": kickoff_iso,
            "CommenceTimeUTC": _clean_str(row.get("CommenceTimeUTC")) or None,
            "home_team": home,
            "away_team": away,
            "elo": {
                "home": round(float(prediction["elo_home"]), 1),
                "away": round(float(prediction["elo_away"]), 1),
            },
            "lambdas": {
                "home": float(prediction["lambda_home"]),
                "away": float(prediction["lambda_away"]),
            },
            "probabilities": {
                "home": float(prediction["prob_home"]),
                "draw": float(prediction["prob_draw"]),
                "away": float(prediction["prob_away"]),
            },
            "over_2_5": float(prediction["prob_over_2_5"]),
            "under_2_5": float(prediction["prob_under_2_5"]),
            "btts_yes": float(prediction["prob_btts_yes"]),
            "btts_no": float(prediction["prob_btts_no"]),
            "top_scores": prediction["top_scores"],
            "odds": odds,
            "odds_source": _clean_str(row.get("OddsSource")) or None,
            "bookmakers": _int_or_none(row.get("BookmakerCount")),
            "fair_odds": fair_odds,
            "value_bets": value_bets,
            "best_value": positives[0] if positives else None,
            "is_value_bet": bool(positives),
            "value_threshold": VALUE_THRESHOLD,
        }

        return get_logo_provider().enrich(result)

    def predict_fixture(self, row: dict, engine: PredictionEngine | None = None) -> dict:
        """
        Prédit un match à partir d'une ligne normalisée de fixtures.

        Méthode publique utilisée par le pipeline d'automatisation
        (backend/update_pipeline.py) et par l'endpoint /api/matches/upcoming.

        Args:
            row: ligne normalisée du DataFrame fixtures.
            engine: moteur éventuellement fourni (pipeline) ; sinon moteur du
                    championnat de l'affiche (ou moteur pooled).

        Returns:
            Dictionnaire de prédiction.
        """
        if engine is None:
            engine = self.engine_for(_clean_str(row.get("Div")))
        return self._predict_row(row, engine=engine)

    def get_upcoming(self, league: str | None = None, value_only: bool = False) -> dict:
        """
        Affiches à venir + prédictions.

        Source prioritaire : data/upcoming_predictions.json (pré-calculé par
        backend/update_pipeline.py, alimenté par The Odds API). L'API répond donc
        instantanément (< 10 ms) sans recalcul ni appel réseau.

        Repli : si le cache est absent/vide, on recalcule à la volée à partir des
        fixtures Football-Data.co.uk.
        """
        if league:
            league = league.strip().upper()

        payload = self._cached_predictions_payload()
        cached_matches = payload.get("matches") or []

        if cached_matches:
            matches = [
                match for match in cached_matches
                if isinstance(match, dict) and match.get("id")
            ]
            if league:
                matches = [m for m in matches if m.get("league_code") == league]
            if value_only:
                matches = [m for m in matches if m.get("is_value_bet")]

            matches.sort(key=lambda m: (m.get("date") or "", m.get("time") or "", m.get("league_code") or ""))
            # Les anciens caches n'ont pas encore `kickoff_utc` : on le dérive
            # à la volée depuis date/time (déjà convertis en heure Paris par le
            # pipeline) pour que le frontend affiche toujours l'instant exact.
            for match in matches:
                if not match.get("kickoff_utc"):
                    match["kickoff_utc"] = _kickoff_iso({
                        "Date": match.get("date"),
                        "Time": match.get("time"),
                        "CommenceTimeUTC": match.get("CommenceTimeUTC"),
                    })
            matches = [get_logo_provider().enrich(match) for match in matches]
            dates = [m["date"] for m in matches if m.get("date")]
            meta = payload.get("meta") or {}
            return {
                "matches": matches,
                "count": len(matches),
                "slate": {
                    "source": meta.get("source", "file-cache"),
                    "projected": False,
                    "note": meta.get(
                        "note", "Prédictions pré-calculées par le pipeline d'automatisation."
                    ),
                    "first_date": min(dates) if dates else None,
                    "last_date": max(dates) if dates else None,
                    "refreshed_at": payload.get("generated_at"),
                    "value_bets": sum(1 for m in matches if m.get("is_value_bet")),
                    "window": meta.get("window"),
                    "quota": meta.get("quota"),
                    "unmapped": meta.get("unmapped", []),
                    "rows_with_odds": meta.get("rows_with_odds"),
                },
            }

        # ---- Repli : calcul à la volée depuis fixtures.csv ----
        fixtures = self.ensure_fixtures()
        if fixtures.empty:
            return {
                "matches": [],
                "count": 0,
                "slate": self._fixtures_meta,
            }

        if league:
            fixtures = fixtures[fixtures["Div"] == league]

        matches = []
        for row in fixtures.to_dict(orient="records"):
            mid = match_id_for(
                _clean_str(row["Div"]),
                row["OriginalDate"],
                _clean_str(row["HomeTeam"]),
                _clean_str(row["AwayTeam"]),
            )
            cached = self._predictions.get(mid)
            if cached is None:
                cached = self._predict_row(row)
                self._predictions[mid] = cached
            matches.append(cached)

        if value_only:
            matches = [m for m in matches if m["is_value_bet"]]

        matches.sort(key=lambda m: (m["date"] or "", m["time"] or "", m["league_code"]))

        dates = [m["date"] for m in matches if m["date"]]
        return {
            "matches": matches,
            "count": len(matches),
            "slate": {
                **self._fixtures_meta,
                "first_date": min(dates) if dates else None,
                "last_date": max(dates) if dates else None,
                "refreshed_at": self._fixtures_loaded_at.isoformat() if self._fixtures_loaded_at else None,
                "value_bets": sum(1 for m in matches if m["is_value_bet"]),
            },
        }

    # ------------------------------------------------------------------
    # Détail d'un match
    # ------------------------------------------------------------------
    def _recent_matches(self, team: str, before, limit: int = 5) -> list[dict]:
        df = self._df
        mask = ((df["HomeTeam"] == team) | (df["AwayTeam"] == team))
        if before is not None:
            mask &= df["Date"] < pd.Timestamp(before)
        sub = df[mask].sort_values("Date").tail(limit)

        out = []
        for row in sub.itertuples(index=False):
            is_home = row.HomeTeam == team
            goals_for = int(row.FTHG) if is_home else int(row.FTAG)
            goals_against = int(row.FTAG) if is_home else int(row.FTHG)
            result = "W" if goals_for > goals_against else ("D" if goals_for == goals_against else "L")
            out.append({
                "date": _iso(row.Date),
                "opponent": row.AwayTeam if is_home else row.HomeTeam,
                "venue": "H" if is_home else "A",
                "goals_for": goals_for,
                "goals_against": goals_against,
                "result": result,
                "league": str(row.Championnat),
            })
        out.reverse()  # le plus récent en premier
        return out

    @staticmethod
    def _form_summary(matches: list[dict]) -> dict:
        wins = sum(1 for m in matches if m["result"] == "W")
        draws = sum(1 for m in matches if m["result"] == "D")
        losses = sum(1 for m in matches if m["result"] == "L")
        goals_for = sum(m["goals_for"] for m in matches)
        goals_against = sum(m["goals_against"] for m in matches)
        played = len(matches)
        return {
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points": wins * 3 + draws,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "avg_goals_for": round(goals_for / played, 2) if played else 0.0,
            "avg_goals_against": round(goals_against / played, 2) if played else 0.0,
        }

    def _elo_series(self, team: str, limit: int = 80) -> list[dict]:
        history = self._engine.elo_history.get(team, [])
        if not history:
            return []
        points = history[-limit:]
        return [{"date": _iso(d), "elo": round(float(elo), 1)} for d, elo in points]

    def get_match(self, match_id: str) -> dict | None:
        fixtures = self.ensure_fixtures()
        target = None
        if not fixtures.empty:
            for row in fixtures.to_dict(orient="records"):
                mid = match_id_for(
                    _clean_str(row["Div"]),
                    row["OriginalDate"],
                    _clean_str(row["HomeTeam"]),
                    _clean_str(row["AwayTeam"]),
                )
                if mid == match_id:
                    target = row
                    break

        cached = self._cached_predictions_index().get(match_id)

        if target is None and cached is None:
            return None

        # Affiche issue de The Odds API (absente de fixtures.csv) : on reconstruit
        # une « ligne fixture » minimale à partir de la prédiction en cache.
        if target is None:
            cached_date = cached.get("date")
            target = {
                "Div": cached.get("league_code", ""),
                "Date": pd.Timestamp(cached_date) if cached_date else pd.Timestamp(date.today()),
                "Time": cached.get("time") or "",
                "HomeTeam": cached.get("home_team", ""),
                "AwayTeam": cached.get("away_team", ""),
                "OriginalDate": cached_date or "",
            }

        match = self._predictions.get(match_id)
        if match is None:
            match = cached
        if match is None:
            match = self._predict_row(target)
        self._predictions[match_id] = match

        self.ensure_model()
        engine = self.engine_for(match.get("league_code", ""))
        home = match["home_team"]
        away = match["away_team"]
        before = target["Date"]

        lambda_home, lambda_away, matrix = engine.score_matrix(home, away)
        size = min(6, matrix.shape[0])  # grille 0-0 .. 5-5

        score_matrix = {
            "goals": list(range(size)),
            "rows": [
                {
                    "goals_home": i,
                    "probabilities": [round(float(matrix[i, j]) * 100, 2) for j in range(size)],
                }
                for i in range(size)
            ],
        }

        recent_home = self._recent_matches(home, before)
        recent_away = self._recent_matches(away, before)

        # Contexte de forme enrichi (10 derniers matchs, splits, séries, repos...)
        from backend.team_context import team_form_context

        form_home = team_form_context(self._df, home, before=before, limit=10, engine=engine)
        form_away = team_form_context(self._df, away, before=before, limit=10, engine=engine)

        # Contexte externe optionnel (effectifs, blessures, compositions, notes).
        # Sans API_FOOTBALL_KEY, le provider renvoie available=False instantanément.
        from backend.context_provider import get_provider

        external = get_provider().get_match_context(
            home, away, match.get("league_code", ""), target["Date"]
        )

        # Indices de force (attaque / défense) pour l'en-tête comparatif
        attack_home, defense_home = engine.team_strengths(home)
        attack_away, defense_away = engine.team_strengths(away)
        forces = {
            "home": {
                "attack": round(float(attack_home), 3),
                "defense": round(float(defense_home), 3),
            },
            "away": {
                "attack": round(float(attack_away), 3),
                "defense": round(float(defense_away), 3),
            },
        }

        return get_logo_provider().enrich({
            **match,
            "score_matrix": score_matrix,
            "elo_history": {
                "home": {"team": home, "points": self._elo_series(home)},
                "away": {"team": away, "points": self._elo_series(away)},
            },
            "recent": {
                "home": {"team": home, "matches": recent_home, "summary": self._form_summary(recent_home)},
                "away": {"team": away, "matches": recent_away, "summary": self._form_summary(recent_away)},
            },
            "form": {"home": form_home, "away": form_away},
            "external": external,
            "forces": forces,
            "kelly": {
                "fraction": 0.25,
                "cap_percent": 3.0,
                "bankroll_default": 100.0,
            },
        })

    # ------------------------------------------------------------------
    # Logos des championnats
    # ------------------------------------------------------------------
    def league_logo(self, league_code: str) -> str | None:
        """URL de l'emblème d'un championnat (None si non disponible)."""
        try:
            from backend.league_logos import get_provider as get_league_logo_provider

            return get_league_logo_provider().logo_for(league_code)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Historique : pronostics vs résultats par journée
    # ------------------------------------------------------------------

    def history_matchdays(self, league: str, limit: int = 6) -> dict:
        """
        Reconstruit les dernières journées d'un championnat avec les prédictions
        telles qu'elles auraient été faites avant les matchs, et les résultats.
        """
        self.ensure_model()
        from backend.history import build_history_cached

        return build_history_cached(self._df, league, limit)

    # ------------------------------------------------------------------
    # Backtesting (page Transparence)
    # ------------------------------------------------------------------
    def _ensure_backtest_files(self):
        """Génère les exports du backtest s'ils sont absents (première exécution)."""
        if os.path.exists(BACKTEST_CSV) and os.path.exists(BACKTEST_JSON):
            return
        with self._backtest_lock:
            if os.path.exists(BACKTEST_CSV) and os.path.exists(BACKTEST_JSON):
                return
            from backtest import run_backtest, save_backtest_results, save_backtest_report

            self.ensure_model()
            metrics, bets, _ = run_backtest(self._df, verbose=False)
            os.makedirs(DATA_DIR, exist_ok=True)
            save_backtest_results(bets, BACKTEST_CSV)
            save_backtest_report(metrics, bets, BACKTEST_JSON)

    def backtest_stats(self, force: bool = False) -> dict:
        if self._backtest_cache is not None and not force:
            return self._backtest_cache

        self._ensure_backtest_files()

        with open(BACKTEST_JSON, "r", encoding="utf-8") as handle:
            report = json.load(handle)
        metrics = report.get("metrics", {})
        bets = pd.read_csv(BACKTEST_CSV)

        # --- Courbe de bankroll (échantillonnée pour rester fluide côté client)
        initial = float(metrics.get("params", {}).get("initial_bankroll", 100.0))
        curve = [{
            "index": 0,
            "date": metrics.get("target_season", ""),
            "label": "Départ",
            "flat": initial,
            "kelly": initial,
        }]

        if not bets.empty:
            step = max(1, len(bets) // 400)
            sampled = bets.iloc[::step]
            for position, row in enumerate(sampled.itertuples(index=False), start=1):
                curve.append({
                    "index": position * step,
                    "date": str(row.Date),
                    "label": str(row.Date),
                    "flat": round(float(row.Bankroll_Flat), 2),
                    "kelly": round(float(row.Bankroll_Kelly), 2),
                })
            # Toujours terminer sur le dernier point réel
            last = bets.iloc[-1]
            curve.append({
                "index": len(bets),
                "date": str(last["Date"]),
                "label": str(last["Date"]),
                "flat": round(float(last["Bankroll_Flat"]), 2),
                "kelly": round(float(last["Bankroll_Kelly"]), 2),
            })

        def _league_rows(by_league: dict) -> list[dict]:
            rows = []
            for league, stats in by_league.items():
                rows.append({
                    "league": league,
                    "bets": stats["bets"],
                    "wins": stats["wins"],
                    "win_rate": stats["win_rate_percent"],
                    "avg_odds": stats["avg_odds"],
                    "roi_flat": stats["flat"]["roi_percent"],
                    "profit_flat": stats["flat"]["profit"],
                    "roi_kelly": stats["kelly"]["roi_percent"],
                    "profit_kelly": stats["kelly"]["profit"],
                })
            rows.sort(key=lambda r: r["roi_flat"], reverse=True)
            return rows

        def _market_rows(by_market: dict) -> list[dict]:
            rows = []
            for market, stats in by_market.items():
                rows.append({
                    "market": market,
                    "label": MARKET_LABELS.get(
                        {"Home": "home", "Draw": "draw", "Away": "away"}.get(market, market), market
                    ),
                    "bets": stats["bets"],
                    "win_rate": stats["win_rate_percent"],
                    "avg_odds": stats["avg_odds"],
                    "roi_flat": stats["flat"]["roi_percent"],
                    "profit_flat": stats["flat"]["profit"],
                    "roi_kelly": stats["kelly"]["roi_percent"],
                    "profit_kelly": stats["kelly"]["profit"],
                })
            rows.sort(key=lambda r: r["bets"], reverse=True)
            return rows

        result = {
            "available": True,
            "season": metrics.get("target_season"),
            "warmup_seasons": metrics.get("warmup_seasons", []),
            "warmup_matches": metrics.get("warmup_matches", 0),
            "matches": metrics.get("predictions", 0),
            "bets": metrics.get("bets", 0),
            "wins": metrics.get("wins", 0),
            "win_rate": metrics.get("win_rate_percent", 0.0),
            "avg_odds": metrics.get("avg_odds", 0.0),
            "avg_ev": metrics.get("avg_ev_percent", 0.0),
            "brier_model": metrics.get("brier_model", 0.0),
            "brier_bookmaker": metrics.get("brier_bookmaker", 0.0),
            "brier_baserate": metrics.get("brier_baserate", 0.0),
            "logloss_model": metrics.get("logloss_model", 0.0),
            "accuracy_1x2": metrics.get("accuracy_1x2_percent", 0.0),
            "strategy_flat": metrics.get("strategy_flat", {}),
            "strategy_kelly": metrics.get("strategy_kelly", {}),
            "by_league": _league_rows(metrics.get("by_league", {})),
            "by_market": _market_rows(metrics.get("by_market", {})),
            "bankroll_curve": curve,
            "params": metrics.get("params", {}),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_bets_recorded": int(len(bets)),
        }
        self._backtest_cache = result
        return result

    def backtest_bets(self, limit: int = 100, offset: int = 0,
                      league: str | None = None, market: str | None = None) -> dict:
        self._ensure_backtest_files()
        bets = pd.read_csv(BACKTEST_CSV)
        if league:
            bets = bets[bets["League"].str.contains(league, case=False, na=False)]
        if market:
            bets = bets[bets["Bet"] == market]
        total = int(len(bets))
        page = bets.iloc[offset: offset + limit]
        rows = page.to_dict(orient="records")
        # Nettoyage des types numpy -> Python natif
        cleaned = []
        for row in rows:
            cleaned.append({
                key: (float(value) if isinstance(value, (int, float)) and key not in ("Won",) else value)
                for key, value in row.items()
            })
        return {"total": total, "limit": limit, "offset": offset, "bets": cleaned}

    def backtest_rolling(self, last_n: int = 30) -> dict:
        """
        ROI glissant sur les N derniers paris simulés (flat et Kelly).

        Contrairement au rapport de saison complet, cet indicateur réagit vite :
        il donne une lecture « forme récente » du modèle, comparable au rendement
        30 jours affiché par les plateformes de pronostics.

        `last_n` = nombre de paris (pas de jours calendaires) — le backtest
        couvre une saison historique, pas un flux continu.
        """
        self._ensure_backtest_files()
        bets = pd.read_csv(BACKTEST_CSV)
        if bets.empty:
            return {"available": False, "window": last_n}

        tail = bets.tail(last_n)
        stake_flat = float(tail["Stake_Flat"].sum())
        profit_flat = float(tail["Profit_Flat"].sum())
        stake_kelly = float(tail["Stake_Kelly"].sum())
        profit_kelly = float(tail["Profit_Kelly"].sum())
        wins = int(tail["Won"].sum())

        return {
            "available": True,
            "window": int(len(tail)),
            "bets": int(len(tail)),
            "wins": wins,
            "win_rate": round(wins / len(tail) * 100, 2) if len(tail) else 0.0,
            "roi_flat": round(profit_flat / stake_flat * 100, 2) if stake_flat else 0.0,
            "roi_kelly": round(profit_kelly / stake_kelly * 100, 2) if stake_kelly else 0.0,
            "profit_flat": round(profit_flat, 2),
            "profit_kelly": round(profit_kelly, 2),
            "first_date": str(pd.Timestamp(tail.iloc[0]["Date"]).date()),
            "last_date": str(pd.Timestamp(tail.iloc[-1]["Date"]).date()),
        }


# Accès direct pratique depuis api.py
service = MatchService.instance()
