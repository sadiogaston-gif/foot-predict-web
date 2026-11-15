"""
backend/wikimedia_logos.py - Logos de clubs via Wikimedia Commons.

Wikimedia Commons héberge les écussons de la plupart des clubs de football
professionnel. L'API est gratuite, sans clé, et sans quota restrictif.

Recherche :
  1. Recherche textuelle "Nom du club logo" dans l'espace fichier (namespace 6)
  2. On retient le premier fichier image (PNG/JPG/SVG)
  3. On récupère l'URL directe via la propriété imageinfo

Mise en cache :
  - Fichier JSON par championnat dans data/logos/wikimedia/
  - TTL 30 jours
"""

from __future__ import annotations

import json
import os
import time
from datetime import date

import requests

from backend.team_mapping import normalize_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "data", "logos", "wikimedia")
CACHE_TTL_SECONDS = 30 * 24 * 3600
TIMEOUT = 20
USER_AGENT = "FootPredict/1.0 (football prediction platform)"


class WikimediaLogoProvider:
    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout
        self._memory: dict[str, dict[str, str]] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _cache_path(self, league_code: str) -> str:
        return os.path.join(CACHE_DIR, f"{league_code}.json")

    def _read_disk(self, league_code: str) -> dict[str, str] | None:
        path = self._cache_path(league_code)
        if not os.path.exists(path):
            return None
        if (time.time() - os.path.getmtime(path)) > CACHE_TTL_SECONDS:
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            mapping = payload.get("mapping") or {}
            return mapping if isinstance(mapping, dict) and mapping else None
        except Exception:
            return None

    def _write_disk(self, league_code: str, mapping: dict[str, str]) -> None:
        if not mapping:
            return
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = self._cache_path(league_code)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"mapping": mapping}, handle, ensure_ascii=False)
        os.replace(tmp, path)

    def _search_image(self, team_name: str) -> str | None:
        """Recherche le fichier image d'un club sur Wikimedia Commons."""
        try:
            r = self.session.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": f'"{team_name}" logo football',
                    "srnamespace": 6,
                    "srlimit": 5,
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            results = r.json().get("query", {}).get("search", [])
        except Exception:
            return None

        for result in results:
            title = result.get("title", "")
            if not title.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".gif")):
                continue
            return self._get_image_url(title)
        return None

    def _get_image_url(self, filename: str) -> str | None:
        """Récupère l'URL directe d'un fichier Wikimedia Commons."""
        try:
            r = self.session.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "imageinfo",
                    "titles": filename,
                    "iiprop": "url",
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            for page in pages.values():
                return page.get("url")
        except Exception:
            return None
        return None

    def logo_for(self, team_name: str, league_code: str) -> str | None:
        """Retourne l'URL du logo d'une équipe via Wikimedia Commons."""
        if not team_name:
            return None

        code = (league_code or "").strip().upper()
        if code in self._memory:
            mapping = self._memory[code]
        else:
            mapping = self._read_disk(code) or {}
            self._memory[code] = mapping

        normalized = normalize_name(team_name)
        if normalized in mapping:
            return mapping[normalized]

        # Recherche sur Wikimedia
        logo = self._search_image(team_name)
        if logo:
            mapping[normalized] = logo
            self._write_disk(league_code, mapping)
            return logo

        return None

    def enrich(self, match: dict) -> dict:
        """Ajoute home_logo / away_logo s'ils manquent."""
        if not isinstance(match, dict):
            return match
        league_code = str(match.get("league_code") or "").strip().upper()
        try:
            if match.get("home_logo") is None:
                match["home_logo"] = self.logo_for(match.get("home_team", ""), league_code)
            if match.get("away_logo") is None:
                match["away_logo"] = self.logo_for(match.get("away_team", ""), league_code)
        except Exception:
            pass
        return match


_provider: WikimediaLogoProvider | None = None


def get_provider() -> WikimediaLogoProvider:
    global _provider
    if _provider is None:
        _provider = WikimediaLogoProvider()
    return _provider
