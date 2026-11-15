"""
backend/league_logos.py - Emblèmes des championnats via Football-Data.org.

L'endpoint `/v4/competitions` renvoie, pour chaque compétition du plan gratuit,
un champ `emblem` (URL d'image). On construit la correspondance
« code Football-Data.co.uk -> URL de l'emblème » et on la met en cache disque
30 jours (une requête seulement).

Les deuxièmes divisions non couvertes par le plan gratuit (F2, D2, I2, SP2, P2)
n'ont pas d'emblème : le frontend affiche un badge généré à la place.
"""

from __future__ import annotations

import json
import os
import time

import requests

from backend.context_provider import FOOTBALL_DATA_COMPETITIONS

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "logos", "leagues.json")
CACHE_TTL_SECONDS = 30 * 24 * 3600
TIMEOUT = 20


class LeagueLogoProvider:
    def __init__(self, api_key: str | None = None, timeout: int = TIMEOUT):
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self._mapping: dict[str, str] | None = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _read_disk(self) -> dict[str, str] | None:
        if not os.path.exists(CACHE_PATH):
            return None
        if (time.time() - os.path.getmtime(CACHE_PATH)) > CACHE_TTL_SECONDS:
            return None
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            mapping = payload.get("mapping") or {}
            return mapping if isinstance(mapping, dict) and mapping else None
        except Exception:
            return None

    def _write_disk(self, mapping: dict[str, str]) -> None:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        tmp = f"{CACHE_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"mapping": mapping}, handle, ensure_ascii=False)
        os.replace(tmp, CACHE_PATH)

    def _download(self) -> dict[str, str]:
        if not self.available:
            return {}
        try:
            response = requests.get(
                f"{FOOTBALL_DATA_BASE}/competitions",
                headers={"X-Auth-Token": self.api_key},
                timeout=self.timeout,
            )
            response.raise_for_status()
            competitions = response.json().get("competitions") or []
        except Exception:
            return {}

        by_competition = {
            competition: league_code
            for league_code, competition in FOOTBALL_DATA_COMPETITIONS.items()
        }
        mapping: dict[str, str] = {}
        for competition in competitions:
            competition_code = competition.get("code")
            emblem = competition.get("emblem")
            league_code = by_competition.get(competition_code)
            if league_code and emblem:
                mapping[league_code] = str(emblem)
        return mapping

    def mapping(self) -> dict[str, str]:
        if self._mapping is not None:
            return self._mapping
        cached = self._read_disk()
        if cached is not None:
            self._mapping = cached
            return cached
        mapping = self._download()
        if mapping:
            self._write_disk(mapping)
        self._mapping = mapping
        return mapping

    def logo_for(self, league_code: str) -> str | None:
        code = (league_code or "").strip().upper()
        return self.mapping().get(code)


_provider: LeagueLogoProvider | None = None


def get_provider() -> LeagueLogoProvider:
    global _provider
    if _provider is None:
        _provider = LeagueLogoProvider(os.environ.get("FOOTBALL_DATA_KEY", ""))
    return _provider
