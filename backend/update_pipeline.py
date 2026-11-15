"""
backend/update_pipeline.py - Pipeline d'automatisation hybride (Phase 3.5)

Architecture hybride retenue :
  * Football-Data.co.uk (CSV de saison) sert UNIQUEMENT à entraîner le modèle
    (classements Elo + forces d'attaque/défense avec Time Decay) ;
  * The Odds API (facultative) sert à récupérer EN TEMPS RÉEL le programme des
    matchs à venir et les cotes 1X2 des bookmakers ;
  * OpenFootball (openfootball/football.json) fournit GRATUITEMENT, SANS CLÉ et
    sans quota, le calendrier des prochaines journées des 5 championnats (dates
    réelles), mais sans cotes bookmaker.

Déroulé :
  Étape A : téléchargement des derniers fichiers CSV de saison (E0, F1, D1, I1,
            SP1) pour intégrer les scores des matchs récemment joués.
  Étape B : construction du programme à venir en fusionnant les sources
            disponibles (The Odds API si clé, fixtures.csv, OpenFootball), avec
            déduplication et priorité aux lignes portant des cotes.
  Étape C : (re)calcul des classements Elo et des forces d'attaque/défense.
  Étape D : génération des prédictions et sauvegarde atomique dans
            data/upcoming_predictions.json (l'API répond ensuite sans recalcul).

Mode sans clé API : si ODDS_API_KEY est absente, le pipeline fonctionne quand
même grâce à fixtures.csv et OpenFootball (vraies dates, pas de cotes ni de
value bets). C'est le mode par défaut recommandé pour un déploiement gratuit.

Gestion des trêves internationales : si aucun match n'est programmé dans les 7
prochains jours, une seconde requête couvre la fenêtre J+7 à J+21 (les « 14 à
21 prochains jours » du cahier des charges), puis J+0 à J+28 en dernier recours.

Gestion d'erreurs : journalisation à chaque étape ; si The Odds API échoue ou si
aucune affiche n'est disponible, l'ancien fichier de prédictions est CONSERVÉ
(jamais écrasé par un fichier vide ou invalide).

Variables d'environnement :
    ODDS_API_KEY                 clé The Odds API (obligatoire pour le mode temps réel)
    ODDS_API_REGIONS             régions des bookmakers (défaut : eu)
    ODDS_REFERENCE_BOOKMAKERS    bookmakers de référence (défaut : pinnacle,bet365)
    ODDS_WINDOW_DAYS             première fenêtre en jours (défaut : 7)
    ODDS_BREAK_WINDOW_END_DAYS   fenêtre de repli en jours (défaut : 21)
    DISPLAY_TIMEZONE             fuseau d'affichage des coups d'envoi (défaut : Europe/Paris)

Usage :
    python backend/update_pipeline.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.fixtures_openfootball import build_fixtures as build_openfootball_fixtures  # noqa: E402
from backend.service import DATA_DIR, LEAGUE_META, service  # noqa: E402
from backend.team_mapping import map_fixture_teams, normalize_name  # noqa: E402
from data_loader import clean_data  # noqa: E402
from prediction_engine import PredictionEngine  # noqa: E402

PREDICTIONS_CACHE = os.path.join(DATA_DIR, "upcoming_predictions.json")
RAW_DIR = os.path.join(ROOT, "data", "raw")
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"

# ---------------------------------------------------------------------------
# Configuration The Odds API
# ---------------------------------------------------------------------------
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_TIMEOUT = 25
ODDS_API_MAX_ATTEMPTS = 3

# sport_key The Odds API -> code Football-Data
SPORT_KEYS: dict[str, str] = {
    "soccer_epl": "E0",
    "soccer_france_ligue_one": "F1",
    "soccer_germany_bundesliga": "D1",
    "soccer_italy_serie_a": "I1",
    "soccer_spain_la_liga": "SP1",
}

REGIONS = os.environ.get("ODDS_API_REGIONS", "eu").strip() or "eu"
MARKETS = "h2h"
ODDS_FORMAT = "decimal"

WINDOW_DAYS = int(os.environ.get("ODDS_WINDOW_DAYS", "7"))
BREAK_WINDOW_END_DAYS = int(os.environ.get("ODDS_BREAK_WINDOW_END_DAYS", "21"))
# Profondeur du calendrier libre OpenFootball (utilisable sans aucune clé API).
FIXTURES_HORIZON_DAYS = int(os.environ.get("FIXTURES_HORIZON_DAYS", "21"))
PREFERRED_BOOKMAKERS = [
    name.strip().lower()
    for name in os.environ.get("ODDS_REFERENCE_BOOKMAKERS", "pinnacle,bet365").split(",")
    if name.strip()
]


class OddsApiError(RuntimeError):
    """Erreur d'appel à The Odds API (clé invalide, quota, réseau...)."""


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


def load_dotenv(path: str | None = None) -> None:
    """
    Charge un fichier .env local (sans dépendance externe) si les variables ne
    sont pas déjà définies dans l'environnement. Utile en développement local ;
    en CI (GitHub Actions), la clé vient des Secrets.
    """
    path = path or os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as exc:
        logging.warning("[UPDATE] Lecture de %s impossible : %s", path, exc)


# ---------------------------------------------------------------------------
# Helpers The Odds API
# ---------------------------------------------------------------------------
def _iso(value: datetime) -> str:
    """Formate un datetime en ISO 8601 UTC (format attendu par The Odds API)."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str | None) -> datetime | None:
    """Parse une date ISO (ex. « 2026-11-21T15:00:00Z ») en datetime UTC."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _odds_api_get(path: str, params: dict) -> tuple[list | dict, dict]:
    """
    Appelle The Odds API avec quelques tentatives en cas d'erreur réseau.

    Returns:
        (payload JSON, quota) où quota contient les en-têtes de consommation.

    Raises:
        OddsApiError: clé refusée, quota épuisé ou erreur persistante.
    """
    url = f"{ODDS_API_BASE}{path}"
    headers = {"User-Agent": "FootPredict/1.0 (+phase3-odds-api)"}
    last_error: Exception | None = None

    for attempt in range(1, ODDS_API_MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=ODDS_API_TIMEOUT, headers=headers)
        except requests.RequestException as exc:
            last_error = exc
            logging.warning(
                "[UPDATE] The Odds API : erreur réseau (tentative %d/%d) : %s",
                attempt, ODDS_API_MAX_ATTEMPTS, exc,
            )
            time.sleep(1.5 * attempt)
            continue

        quota = {
            "remaining": response.headers.get("x-requests-remaining"),
            "used": response.headers.get("x-requests-used"),
            "last": response.headers.get("x-requests-last"),
        }

        if response.status_code == 200:
            try:
                return response.json(), quota
            except ValueError as exc:
                raise OddsApiError(f"Réponse JSON invalide : {exc}") from exc

        body = response.text[:300]
        if response.status_code in (401, 403):
            raise OddsApiError(
                f"clé ODDS_API_KEY refusée (HTTP {response.status_code}) : {body}"
            )
        if response.status_code == 429:
            raise OddsApiError(
                f"quota The Odds API épuisé (HTTP 429, restant={quota.get('remaining')}) : {body}"
            )
        if response.status_code == 422:
            # Paramètres refusés : on laisse l'appelant décider (repli sans filtre de dates).
            raise OddsApiError(f"paramètres refusés (HTTP 422) : {body}")

        last_error = OddsApiError(f"HTTP {response.status_code} : {body}")
        logging.warning(
            "[UPDATE] The Odds API : %s (tentative %d/%d)",
            last_error, attempt, ODDS_API_MAX_ATTEMPTS,
        )
        time.sleep(1.0 * attempt)

    raise OddsApiError(f"The Odds API indisponible : {last_error}")


def fetch_sport_events(
    sport_key: str,
    start: datetime,
    end: datetime,
    api_key: str,
) -> tuple[list[dict], dict]:
    """
    Récupère les événements (matchs) et cotes h2h d'un championnat sur une fenêtre.

    Si l'API refuse les paramètres de fenêtre (HTTP 422), on refait l'appel sans
    filtre de dates et on filtre localement : la robustesse prime sur l'élégance.
    """
    params = {
        "apiKey": api_key,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
        "dateFormat": "iso",
        "commenceTimeFrom": _iso(start),
        "commenceTimeTo": _iso(end),
    }
    try:
        payload, quota = _odds_api_get(f"/sports/{sport_key}/odds", params)
    except OddsApiError as exc:
        if "422" not in str(exc):
            raise
        logging.warning(
            "[UPDATE] Fenêtre refusée pour %s (422) : nouvel appel sans filtre de dates.", sport_key
        )
        params.pop("commenceTimeFrom", None)
        params.pop("commenceTimeTo", None)
        payload, quota = _odds_api_get(f"/sports/{sport_key}/odds", params)

    events = payload if isinstance(payload, list) else []
    filtered = []
    for event in events:
        commence = _parse_iso(event.get("commence_time"))
        if commence is None or not (start <= commence <= end):
            continue
        filtered.append(event)
    return filtered, quota


# ---------------------------------------------------------------------------
# Cotes : consensus du marché et bookmaker de référence
# ---------------------------------------------------------------------------
def _outcome_slot(outcome_name: str, home_api: str, away_api: str) -> str | None:
    """Convertit un libellé d'issue The Odds API en « home », « draw » ou « away »."""
    normalized = normalize_name(outcome_name)
    if not normalized:
        return None
    if normalized == normalize_name(home_api):
        return "home"
    if normalized == normalize_name(away_api):
        return "away"
    if "draw" in normalized:
        return "draw"
    return None


def _event_odds(event: dict) -> dict | None:
    """
    Calcule les cotes 1X2 d'un événement.

    Stratégie : on agrège toutes les cotes h2h des bookmakers, puis on retient en
    priorité un bookmaker de référence (Pinnacle, puis Bet365) ; à défaut, on
    utilise la moyenne du marché (consensus).

    Returns:
        {"home": float, "draw": float, "away": float, "source": str, "bookmakers": int}
        ou None si aucune cote exploitable.
    """
    home_api = str(event.get("home_team", ""))
    away_api = str(event.get("away_team", ""))
    quotes: list[dict] = []

    for bookmaker in event.get("bookmakers") or []:
        bookmaker_key = str(bookmaker.get("key", "")).lower()
        for market in bookmaker.get("markets") or []:
            if market.get("key") != "h2h":
                continue
            prices: dict[str, list[float]] = {"home": [], "draw": [], "away": []}
            for outcome in market.get("outcomes") or []:
                slot = _outcome_slot(str(outcome.get("name", "")), home_api, away_api)
                if slot is None:
                    continue
                try:
                    price = float(outcome.get("price"))
                except (TypeError, ValueError):
                    continue
                if price > 1.0:
                    prices[slot].append(price)
            if all(prices[slot] for slot in ("home", "draw", "away")):
                quotes.append({
                    "key": bookmaker_key,
                    "home": mean(prices["home"]),
                    "draw": mean(prices["draw"]),
                    "away": mean(prices["away"]),
                })

    if not quotes:
        return None

    for preferred in PREFERRED_BOOKMAKERS:
        for quote in quotes:
            if quote["key"] == preferred:
                return {
                    "home": round(quote["home"], 3),
                    "draw": round(quote["draw"], 3),
                    "away": round(quote["away"], 3),
                    "source": preferred,
                    "bookmakers": len(quotes),
                }

    return {
        "home": round(mean(q["home"] for q in quotes), 3),
        "draw": round(mean(q["draw"] for q in quotes), 3),
        "away": round(mean(q["away"] for q in quotes), 3),
        "source": "consensus",
        "bookmakers": len(quotes),
    }


# ---------------------------------------------------------------------------
# Construction du tableau des affiches
# ---------------------------------------------------------------------------
def build_fixtures_from_odds_api(api_key: str) -> tuple[pd.DataFrame, dict]:
    """
    Interroge The Odds API pour les 5 championnats et renvoie un DataFrame
    compatible avec backend.service.predict_fixture.

    La fenêtre « 7 jours » est tentée d'abord ; si elle est vide (trêve
    internationale), on élargit à J+7 → J+21, puis à J+0 → J+28.

    Returns:
        (DataFrame des affiches, méta-données de collecte).

    Raises:
        OddsApiError: si la clé est refusée ou le quota épuisé.
    """
    now = datetime.now(timezone.utc)
    windows = [
        (now, now + timedelta(days=WINDOW_DAYS), f"{WINDOW_DAYS}_jours"),
        (now + timedelta(days=WINDOW_DAYS), now + timedelta(days=BREAK_WINDOW_END_DAYS),
         f"{WINDOW_DAYS}_a_{BREAK_WINDOW_END_DAYS}_jours"),
        (now, now + timedelta(days=max(28, BREAK_WINDOW_END_DAYS)), "0_a_28_jours"),
    ]

    quota_seen: dict = {}
    events: list[tuple[str, dict]] = []
    chosen_label = ""

    for start, end, label in windows:
        collected: list[tuple[str, dict]] = []
        for sport_key, league_code in SPORT_KEYS.items():
            sport_events, quota = fetch_sport_events(sport_key, start, end, api_key)
            quota_seen = quota or quota_seen
            logging.info(
                "[UPDATE] The Odds API : %s (%s) -> %d événement(s).",
                sport_key, league_code, len(sport_events),
            )
            collected.extend((league_code, event) for event in sport_events)
        logging.info(
            "[UPDATE] Fenêtre %s : %d événement(s) au total (%s -> %s).",
            label, len(collected), _iso(start), _iso(end),
        )
        if collected:
            events = collected
            chosen_label = label
            break

    if not events:
        return pd.DataFrame(), {
            "source": "the-odds-api",
            "window": None,
            "events": 0,
            "note": "The Odds API n'a renvoyé aucun match sur les fenêtres interrogées.",
            "quota": quota_seen,
        }

    local_tz = ZoneInfo(os.environ.get("DISPLAY_TIMEZONE", "Europe/Paris"))
    rows: list[dict] = []
    unmapped: list[str] = []
    skipped = 0

    for league_code, event in events:
        commence = _parse_iso(event.get("commence_time"))
        odds = _event_odds(event)
        if commence is None or odds is None:
            skipped += 1
            continue

        home_api = str(event.get("home_team", "")).strip()
        away_api = str(event.get("away_team", "")).strip()
        mapping = map_fixture_teams(home_api, away_api, league_code)
        if mapping["unmapped"]:
            unmapped.extend(mapping["unmapped"])
            logging.warning(
                "[UPDATE] Équipe(s) non reconnue(s) (%s) : %s — prédiction avec priors.",
                league_code, ", ".join(mapping["unmapped"]),
            )

        kickoff_local = commence.astimezone(local_tz)
        rows.append({
            "Div": league_code,
            "Date": pd.Timestamp(kickoff_local.date()),
            "Time": kickoff_local.strftime("%H:%M"),
            "HomeTeam": mapping["home"] or home_api,
            "AwayTeam": mapping["away"] or away_api,
            "B365H": odds["home"],
            "B365D": odds["draw"],
            "B365A": odds["away"],
            "OriginalDate": kickoff_local.strftime("%Y-%m-%d"),
            "OddsSource": odds["source"],
            "BookmakerCount": odds["bookmakers"],
            "CommenceTimeUTC": _iso(commence),
        })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = (
            frame.drop_duplicates(subset=["Div", "OriginalDate", "HomeTeam", "AwayTeam"])
            .sort_values(["Date", "Time", "Div"])
            .reset_index(drop=True)
        )

    meta = {
        "source": "the-odds-api",
        "window": chosen_label,
        "events": int(len(frame)),
        "skipped": skipped,
        "unmapped": sorted(set(unmapped)),
        "quota": quota_seen,
        "regions": REGIONS,
        "markets": MARKETS,
        "note": (
            "Affiches et cotes 1X2 temps réel issues de The Odds API "
            f"(fenêtre {chosen_label}, consensus {REGIONS.upper()})."
        ),
    }
    logging.info("[UPDATE] The Odds API : %d affiche(s) exploitable(s), %d ignorée(s).",
                 len(frame), skipped)
    return frame, meta


# ---------------------------------------------------------------------------
# Étape A - Téléchargement des dernières saisons (intégration des scores)
# ---------------------------------------------------------------------------
def step_a_download_latest_results(league_codes: list[str]) -> int:
    """
    Télécharge les fichiers CSV de TOUTES les saisons configurées pour chaque
    championnat ciblé. Cela garantit qu'un championnat nouvellement ajouté
    dispose immédiatement de son historique d'entraînement complet.

    Returns:
        Le nombre de fichiers téléchargés avec succès.
    """
    from data_loader import download_season_league
    from config import SEASONS

    downloaded = 0
    for code in league_codes:
        for season in SEASONS:
            df = download_season_league(season, code, raw_dir=RAW_DIR)
            if df is not None and not df.empty:
                logging.info(
                    "[UPDATE] Étape A : saison %s / %s -> %d matchs téléchargés.",
                    season, code, len(df),
                )
                downloaded += 1
            else:
                logging.warning(
                    "[UPDATE] Étape A : échec ou fichier vide pour la saison %s / %s.",
                    season, code,
                )
    return downloaded


# ---------------------------------------------------------------------------
# Étape C - Données d'entraînement + moteur
# ---------------------------------------------------------------------------
def load_cached_training_data() -> pd.DataFrame | None:
    """
    Construit le DataFrame d'entraînement à partir du cache brut local
    (data/raw/*.csv), qui inclut les dernières saisons téléchargées à l'étape A.

    Returns:
        DataFrame nettoyé (via data_loader.clean_data) ou None si aucun cache.
    """
    if not os.path.isdir(RAW_DIR):
        return None

    frames = []
    for fname in sorted(os.listdir(RAW_DIR)):
        if not fname.lower().endswith(".csv"):
            continue
        stem = fname[: -len(".csv")]
        if "_" not in stem:
            continue
        season, code = stem.split("_", 1)
        path = os.path.join(RAW_DIR, fname)
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            logging.warning("[UPDATE] Cache illisible : %s (%s)", fname, exc)
            continue
        if df.empty:
            continue
        df = df.copy()
        df["Saison"] = season
        df["Championnat"] = LEAGUE_META.get(code, {}).get("name", code)
        df["CodeChampionnat"] = code
        frames.append(df)

    if not frames:
        return None
    return clean_data(pd.concat(frames, ignore_index=True))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _fallback_fixtures() -> tuple[pd.DataFrame, dict]:
    """Affiches du fichier fixtures.csv de Football-Data (avec cotes Bet365)."""
    logging.info("[UPDATE] Lecture des affiches fixtures.csv de Football-Data.co.uk.")
    fixtures = service.ensure_fixtures(force=True)
    meta = {
        "source": "fixtures.csv",
        **(getattr(service, "_fixtures_meta", {}) or {}),
        "note": (getattr(service, "_fixtures_meta", {}) or {}).get(
            "note", "Affiches issues de fixtures.csv."
        ),
    }
    return fixtures, meta


# ---------------------------------------------------------------------------
# Fusion des sources d'affiches : The Odds API / fixtures.csv / OpenFootball
# ---------------------------------------------------------------------------
def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("", "nan", "none") else text


def _normalise_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Garantit les colonnes attendues par service.predict_fixture."""
    out = frame.copy()
    out["Date"] = pd.to_datetime(out.get("Date"), errors="coerce")
    for column, default in (
        ("Time", ""),
        ("OddsSource", None),
        ("BookmakerCount", 0),
        ("B365H", None),
        ("B365D", None),
        ("B365A", None),
    ):
        if column not in out.columns:
            out[column] = default
    if "OriginalDate" not in out.columns:
        out["OriginalDate"] = out["Date"].dt.strftime("%Y-%m-%d")
    return out


def _has_odds(row: dict) -> bool:
    """Vrai si la ligne contient au moins une cote 1X2 exploitable."""
    for column in ("B365H", "B365D", "B365A"):
        try:
            value = float(row.get(column))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 1.0:
            return True
    return False


def merge_fixture_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Fusionne plusieurs sources d'affiches en supprimant les doublons.

    Clé de déduplication : (championnat, équipe domicile, équipe extérieur).
    En cas de doublon, la ligne contenant des cotes bookmaker est conservée
    (elle permet de détecter les value bets).
    """
    merged: dict[tuple, dict] = {}
    for frame in frames:
        if frame is None or frame.empty:
            continue
        for row in frame.to_dict(orient="records"):
            div = _clean(row.get("Div"))
            home = _clean(row.get("HomeTeam"))
            away = _clean(row.get("AwayTeam"))
            if not (div and home and away):
                continue
            key = (div, home, away)
            current = merged.get(key)
            if current is None or (_has_odds(row) and not _has_odds(current)):
                merged[key] = row

    rows = list(merged.values())
    rows.sort(key=lambda item: (str(item.get("Date")), str(item.get("Div")), str(item.get("Time"))))
    return pd.DataFrame(rows)


def build_all_fixtures(api_key: str) -> tuple[pd.DataFrame, dict]:
    """
    Construit le programme des matchs à venir en fusionnant TOUTES les sources
    disponibles :

      1. The Odds API (si ODDS_API_KEY est fournie) : cotes temps réel ;
      2. fixtures.csv de Football-Data : cotes Bet365 quand les 5 grands
         championnats y figurent ;
      3. OpenFootball (openfootball/football.json) : calendrier libre, sans clé,
         avec les vraies dates des prochaines journées.

    La fusion privilégie les lignes porteuses de cotes, puis déduplique.
    """
    frames: list[pd.DataFrame] = []
    metas: list[dict] = []

    # 1) The Odds API (facultative)
    if api_key:
        try:
            odds_frame, odds_meta = build_fixtures_from_odds_api(api_key)
            if odds_frame is not None and not odds_frame.empty:
                frames.append(_normalise_frame(odds_frame))
                metas.append(odds_meta)
        except OddsApiError as exc:
            logging.error("[UPDATE] The Odds API indisponible : %s", exc)
        except Exception:
            logging.exception("[UPDATE] Erreur inattendue lors de l'appel à The Odds API.")
    else:
        logging.info(
            "[UPDATE] Aucune ODDS_API_KEY : utilisation du calendrier libre OpenFootball "
            "(sans cotes)."
        )

    # 2) fixtures.csv (cotes Bet365 quand disponible)
    try:
        csv_frame, csv_meta = _fallback_fixtures()
        if csv_frame is not None and not csv_frame.empty:
            frames.append(_normalise_frame(csv_frame))
            metas.append(csv_meta)
    except Exception:
        logging.exception("[UPDATE] fixtures.csv indisponible.")

    # 3) OpenFootball (calendrier libre, sans clé API)
    try:
        openfootball_rows, openfootball_meta = build_openfootball_fixtures(
            horizon_days=FIXTURES_HORIZON_DAYS
        )
        if openfootball_rows:
            frames.append(_normalise_frame(pd.DataFrame(openfootball_rows)))
            metas.append(openfootball_meta)
    except Exception:
        logging.exception("[UPDATE] Calendrier OpenFootball indisponible.")

    merged = merge_fixture_frames(frames)
    sources = list(dict.fromkeys(str(meta.get("source")) for meta in metas))
    with_odds = (
        sum(1 for row in merged.to_dict(orient="records") if _has_odds(row))
        if not merged.empty else 0
    )

    meta = {
        "source": "hybrid:" + "+".join(sources) if sources else "none",
        "sources": sources,
        "count": int(len(merged)),
        "rows_with_odds": int(with_odds),
        "horizon_days": FIXTURES_HORIZON_DAYS,
        "note": (
            "Affiches fusionnées (The Odds API si clé, fixtures.csv, OpenFootball). "
            f"{with_odds} affiche(s) avec cotes bookmaker ; "
            f"profondeur {FIXTURES_HORIZON_DAYS} jours."
            + (
                ""
                if with_odds
                else " Aucune cote disponible pour le moment : les value bets seront calculés "
                     "dès la publication des cotes Bet365 dans fixtures.csv, ou en configurant "
                     "ODDS_API_KEY."
            )
        ),
    }
    logging.info(
        "[UPDATE] Fusion : %d affiche(s), dont %d avec cotes (sources: %s).",
        len(merged), with_odds, ", ".join(sources) or "aucune",
    )
    return merged, meta


def run_pipeline() -> dict:
    """
    Exécute le pipeline complet : A -> B (Odds API ou repli) -> C -> D.

    Returns:
        dict de suivi : {"status": "ok"|"skipped", ...}.
    """
    logging.info("[UPDATE] Début du pipeline de mise à jour des prédictions.")

    api_key = os.environ.get("ODDS_API_KEY", "").strip()

    # Étape A : intégrer les scores récents
    league_codes = sorted(LEAGUE_META.keys())
    downloaded = step_a_download_latest_results(league_codes)
    logging.info("[UPDATE] Étape A : %d fichiers de saison traités.", downloaded)

    # Étape B : affiches + cotes, fusion de toutes les sources disponibles
    fixtures, meta = build_all_fixtures(api_key)

    if fixtures is None or fixtures.empty:
        # Trêve internationale / sources indisponibles : on ne touche pas au
        # fichier existant (conservation de l'ancien fichier valide).
        logging.warning(
            "[UPDATE] Aucune affiche disponible : conservation du fichier predictions existant."
        )
        return {"status": "skipped", "reason": "fixtures_unavailable", "downloaded": downloaded}

    # Étape C : (re)calcul du moteur
    training_df = load_cached_training_data()
    if training_df is None or training_df.empty:
        raise RuntimeError("Aucune donnée d'entraînement exploitable trouvée dans data/raw/.")

    # Un moteur par championnat si activé (config.USE_PER_LEAGUE_ENGINES)
    engines, pooled_engine = service.train_engines(training_df)
    logging.info(
        "[UPDATE] Étape C : moteurs entraînés sur %d matchs (%d moteurs, eq. pooled=%d).",
        len(training_df), len(engines), len(pooled_engine.teams),
    )

    # Étape D : prédictions pour toutes les affiches
    rows = fixtures.to_dict(orient="records")
    matches = []
    for row in rows:
        league_code = str(row.get("Div") or "").strip().upper()
        engine = engines.get(league_code) or pooled_engine
        matches.append(service.predict_fixture(row, engine=engine))
    matches = [match for match in matches if match and match.get("id")]
    if not matches:
        logging.warning(
            "[UPDATE] Aucune prédiction générée : conservation du fichier predictions existant."
        )
        return {"status": "skipped", "reason": "no_predictions", "downloaded": downloaded}

    save_predictions(matches, meta)

    logging.info(
        "[UPDATE] Étape D : %d prédictions générées (source : %s).",
        len(matches), meta.get("source", "?"),
    )
    return {
        "status": "ok",
        "count": len(matches),
        "downloaded": downloaded,
        "source": meta.get("source", "?"),
        "window": meta.get("window"),
        "unmapped": meta.get("unmapped", []),
        "quota_remaining": (meta.get("quota") or {}).get("remaining"),
    }


# ---------------------------------------------------------------------------
# Sauvegarde atomique
# ---------------------------------------------------------------------------
def save_predictions(matches: list[dict], meta: dict | None = None) -> None:
    """
    Sauvegarde les prédictions dans data/upcoming_predictions.json (écriture
    atomique via fichier temporaire + os.replace), avec les méta-données de
    collecte (source, fenêtre, quota The Odds API...).
    """
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(matches),
        "meta": meta or {},
        "matches": matches,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp_path = os.path.join(DATA_DIR, f".upcoming_predictions.json.{os.getpid()}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, PREDICTIONS_CACHE)
    logging.info("[UPDATE] Prédictions sauvegardées dans %s", PREDICTIONS_CACHE)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def main() -> int:
    setup_logging()
    load_dotenv()
    try:
        result = run_pipeline()
    except Exception:
        logging.exception(
            "[UPDATE] Le pipeline a échoué : l'ancien fichier predictions est conservé."
        )
        return 1
    logging.info("[UPDATE] Pipeline terminé : %s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
