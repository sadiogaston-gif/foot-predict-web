"""
backend/fixtures_openfootball.py - Source d'affiches LIBRE et SANS CLÉ API.

Le dépôt GitHub « openfootball/football.json » publie, pour chaque saison, des
fichiers JSON statiques contenant le calendrier complet des grands championnats
(dates, heures, équipes) — y compris les matchs à venir.

C'est une alternative gratuite, sans inscription et sans quota, à The Odds API
pour connaître les prochaines journées. Elle ne fournit en revanche AUCUNE cote
bookmaker : les prédictions sont calculées, mais les value bets ne peuvent pas
être détectés tant qu'une source de cotes (fixtures.csv ou The Odds API) n'est
pas disponible.

Fichiers utilisés (branche master, dossier de saison « AAAA-AA ») :
    E0  -> en.1.json   (Premier League)
    F1  -> fr.1.json   (Ligue 1)
    D1  -> de.1.json   (Bundesliga)
    I1  -> it.1.json   (Serie A)
    SP1 -> es.1.json   (La Liga)
    P1  -> pt.1.json   (Primeira Liga)
    N1  -> nl.1.json   (Eredivisie)

URL de base : https://raw.githubusercontent.com/openfootball/football.json/master

Cache local : data/raw/openfootball/{saison}_{fichier}.json (TTL 12 h) afin de
ne pas re-télécharger à chaque exécution.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timedelta

import requests

from backend.team_mapping import map_fixture_teams

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"

# Code Football-Data -> nom de fichier OpenFootball
LEAGUE_FILES: dict[str, str] = {
    "E0": "en.1.json",
    "F1": "fr.1.json",
    "D1": "de.1.json",
    "I1": "it.1.json",
    "SP1": "es.1.json",
    "P1": "pt.1.json",
    "N1": "nl.1.json",
    # Deuxièmes divisions : seule la Championship est publiée par OpenFootball
    "E1": "en.2.json",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "data", "raw", "openfootball")
CACHE_TTL_SECONDS = 12 * 3600
REQUEST_TIMEOUT = 25
MAX_ATTEMPTS = 2


def current_season_label(today: date | None = None) -> str:
    """
    Libellé de la saison en cours au format utilisé par OpenFootball.

    La saison démarre en juillet : en novembre 2026 -> « 2026-27 ».
    """
    today = today or date.today()
    start_year = today.year if today.month >= 7 else today.year - 1
    end_short = (start_year + 1) % 100
    return f"{start_year}-{end_short:02d}"


def _cache_path(season: str, filename: str) -> str:
    return os.path.join(CACHE_DIR, f"{season}_{filename}")


def _read_cache(season: str, filename: str, allow_stale: bool) -> dict | None:
    path = _cache_path(season, filename)
    if not os.path.exists(path):
        return None
    if not allow_stale and (time.time() - os.path.getmtime(path)) > CACHE_TTL_SECONDS:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logging.warning("[OPENFOOTBALL] Cache illisible %s : %s", path, exc)
        return None


def _download(season: str, filename: str) -> dict | None:
    url = f"{BASE_URL}/{season}/{filename}"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 404:
                logging.info(
                    "[OPENFOOTBALL] %s/%s indisponible (404) : saison pas encore publiée.",
                    season, filename,
                )
                return None
            response.raise_for_status()
            payload = response.json()
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(_cache_path(season, filename), "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
            return payload
        except Exception as exc:
            logging.warning(
                "[OPENFOOTBALL] Téléchargement %s/%s échoué (tentative %d/%d) : %s",
                season, filename, attempt, MAX_ATTEMPTS, exc,
            )
            time.sleep(1.0 * attempt)
    return None


def _load_league(season: str, filename: str, force_refresh: bool) -> dict | None:
    """Charge un championnat : cache frais, sinon téléchargement, sinon cache périmé."""
    if not force_refresh:
        cached = _read_cache(season, filename, allow_stale=False)
        if cached is not None:
            return cached
    downloaded = _download(season, filename)
    if downloaded is not None:
        return downloaded
    return _read_cache(season, filename, allow_stale=True)


def build_fixtures(
    horizon_days: int = 21,
    today: date | None = None,
    force_refresh: bool = False,
) -> tuple[list[dict], dict]:
    """
    Construit les affiches à venir des 5 championnats à partir d'OpenFootball.

    Args:
        horizon_days: profondeur de l'horizon (par défaut 21 jours).
        today: date de référence (par défaut aujourd'hui).
        force_refresh: ignore le cache frais et re-télécharge.

    Returns:
        (lignes prêtes pour service.predict_fixture, méta-données).
        Chaque ligne contient : Div, Date, Time, HomeTeam, AwayTeam,
        OriginalDate, OddsSource="openfootball", BookmakerCount=0.
    """
    today = today or date.today()
    horizon_end = today + timedelta(days=horizon_days)
    season = current_season_label(today)

    rows: list[dict] = []
    per_league: dict[str, int] = {}
    unmapped: list[str] = []
    unavailable: list[str] = []

    for league_code, filename in LEAGUE_FILES.items():
        payload = _load_league(season, filename, force_refresh)
        if payload is None:
            unavailable.append(league_code)
            per_league[league_code] = 0
            continue

        count = 0
        for match in payload.get("matches", []):
            raw_date = match.get("date")
            if not raw_date:
                continue
            try:
                match_date = date.fromisoformat(str(raw_date))
            except ValueError:
                continue

            # On ne garde que la fenêtre [aujourd'hui ; aujourd'hui + horizon]
            if match_date < today or match_date > horizon_end:
                continue
            # Un score signifie que le match est déjà joué
            if match.get("score"):
                continue

            mapping = map_fixture_teams(
                str(match.get("team1", "")), str(match.get("team2", "")), league_code
            )
            if mapping["unmapped"]:
                unmapped.extend(mapping["unmapped"])
                logging.warning(
                    "[OPENFOOTBALL] Équipe(s) non reconnue(s) (%s) : %s",
                    league_code, ", ".join(mapping["unmapped"]),
                )

            rows.append({
                "Div": league_code,
                "Date": match_date,
                "Time": str(match.get("time") or "")[:5],
                "HomeTeam": mapping["home"] or str(match.get("team1", "")).strip(),
                "AwayTeam": mapping["away"] or str(match.get("team2", "")).strip(),
                "OriginalDate": match_date.isoformat(),
                "OddsSource": "openfootball",
                "BookmakerCount": 0,
                "Round": str(match.get("round") or ""),
            })
            count += 1

        per_league[league_code] = count

    rows.sort(key=lambda item: (item["Div"], item["Date"], item["Time"]))

    meta = {
        "source": "openfootball",
        "season": season,
        "horizon_days": horizon_days,
        "horizon_end": horizon_end.isoformat(),
        "events": len(rows),
        "per_league": per_league,
        "unmapped": sorted(set(unmapped)),
        "unavailable": unavailable,
        "note": (
            "Calendrier libre OpenFootball (openfootball/football.json), sans clé API. "
            f"Saison {season}, fenêtre de {horizon_days} jours, sans cotes bookmaker."
        ),
    }
    logging.info(
        "[OPENFOOTBALL] %d affiche(s) à venir (%s -> %s), saison %s.",
        len(rows), today.isoformat(), horizon_end.isoformat(), season,
    )
    return rows, meta
