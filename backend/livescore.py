"""
backend/livescore.py - Client pour l'API livescoreFootball (rezarahiminia/livescoreFootball)

Fournit les scores en direct, fixtures, classements, résumés de match et
play-by-play depuis l'API publique gratuite (pas de clé API requise).

Documentation de l'API : https://github.com/rezarahiminia/livescoreFootball
Site de démo : https://worldcup26.ir/

Architecture :
  - Un listener externe écrit dans MongoDB (séparé de ce projet)
  - Ce client lit uniquement les données publiées (lecture seule)
  - Aucun appel upstream pendant la requête client (côté livescoreFootball)

Endpoints utilisés :
  GET /get/soccer/leagues?kind=club&available=true
  GET /get/soccer/{slug}/scoreboard?dates=YYYYMMDD
  GET /get/soccer/{slug}/fixtures?status=all&from=YYYYMMDD&to=YYYYMMDD
  GET /get/soccer/{slug}/summary?event={eventId}
  GET /get/soccer/{slug}/events/{eventId}/plays
"""

from __future__ import annotations

import os
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# URL de base de l'API livescoreFootball.
# En développement : http://localhost:3050
# En production      : https://worldcup26.ir  (à confirmer par l'hébergeur de l'API)
LIVESCORE_BASE = os.environ.get(
    "LIVESCORE_BASE_URL", "https://worldcup26.ir"
).rstrip("/")

DEFAULT_TIMEOUT = 20

# ---------------------------------------------------------------------------
# Mapping des codes Foot Predict vers les slugs livescoreFootball
#
# Slugs connus depuis le README du projet :
#   eng.1 = Premier League, eng.2 = Championship
#   esp.1 = LaLiga,         esp.2 = LaLiga 2
# Les autres sont des conventions probables (à vérifier au besoin).
# ---------------------------------------------------------------------------

LEAGUE_SLUG_MAP: dict[str, str] = {
    "E0": "eng.1",   # Premier League (Angleterre)
    "E1": "eng.2",   # Championship (Angleterre)
    "F1": "fra.1",   # Ligue 1 (France)
    "F2": "fra.2",   # Ligue 2 (France)
    "D1": "deu.1",   # Bundesliga (Allemagne)
    "D2": "deu.2",   # 2. Bundesliga (Allemagne)
    "I1": "ita.1",   # Serie A (Italie)
    "I2": "ita.2",   # Serie B (Italie)
    "SP1": "esp.1",  # LaLiga (Espagne)
    "SP2": "esp.2",  # Segunda División / LaLiga 2 (Espagne)
    "P1": "prt.1",   # Primeira Liga (Portugal)
    "P2": "prt.2",   # Liga Portugal 2 (Portugal)
    "N1": "nld.1",   # Eredivisie (Pays-Bas)
    "B1": "bel.1",   # Jupiler Pro League (Belgique)
    "T1": "tur.1",   # Süper Lig (Turquie)
}


def _slug_for(league_code: str) -> str | None:
    """Retourne le slug livescoreFootball pour un code Foot Predict, ou None."""
    return LEAGUE_SLUG_MAP.get(league_code.strip().upper())


# ---------------------------------------------------------------------------
# Appel HTTP vers l'API livescoreFootball
# ---------------------------------------------------------------------------

def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Effectue un GET vers l'API livescoreFootball.

    Retourne le JSON parsé ou None en cas d'erreur (réseau, statut non-200,
    JSON invalide). Aucune exception ne remonte.
    """
    url = f"{LIVESCORE_BASE}{path}"
    try:
        response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[LIVE SCORE] Erreur {path}: {exc}")
        return None


def _extract_list(data: Any) -> list[dict[str, Any]]:
    """Extrait une liste d'objets depuis une réponse JSON (liste directe ou dict)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("leagues", "matches", "games", "fixtures", "events", "plays",
                    "data", "results", "content"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


# ---------------------------------------------------------------------------
# Fonctions publiques
# ---------------------------------------------------------------------------

def get_available_leagues() -> list[dict[str, Any]]:
    """Liste des compétitions disponibles sur livescoreFootball."""
    data = _get("/get/soccer/leagues", params={"kind": "club", "available": "true"})
    return _extract_list(data)


def get_scoreboard(
    league_code: str,
    date_str: str | None = None,
) -> list[dict[str, Any]]:
    """Matchs d'une ligue pour une date donnée (format YYYYMMDD).

    Si date_str est None, retourne les matchs du jour / en cours.
    """
    slug = _slug_for(league_code)
    if not slug:
        return []
    params: dict[str, Any] = {}
    if date_str:
        params["dates"] = date_str
    data = _get(f"/get/soccer/{slug}/scoreboard", params=params)
    return _extract_list(data)


def get_fixtures(
    league_code: str,
    status: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Calendrier et résultats d'une ligue."""
    slug = _slug_for(league_code)
    if not slug:
        return []
    params: dict[str, Any] = {"status": status}
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    data = _get(f"/get/soccer/{slug}/fixtures", params=params)
    return _extract_list(data)


def get_match_summary(
    league_code: str,
    event_id: str,
) -> dict[str, Any] | None:
    """Résumé complet d'un match (buteurs, stats, timeline, etc.)."""
    slug = _slug_for(league_code)
    if not slug:
        return None
    return _get(f"/get/soccer/{slug}/summary", params={"event": event_id})


def get_match_events(
    league_code: str,
    event_id: str,
) -> list[dict[str, Any]]:
    """Play-by-play d'un match (buts, remplacements, minute, etc.)."""
    slug = _slug_for(league_code)
    if not slug:
        return []
    data = _get(f"/get/soccer/{slug}/events/{event_id}/plays")
    return _extract_list(data)
