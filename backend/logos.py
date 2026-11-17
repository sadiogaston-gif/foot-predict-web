"""
backend/logos.py - Logos (écussons) des clubs via Football-Data.org.

Football-Data.org expose un champ `crest` (URL d'image) pour chaque équipe.
On construit, par championnat, une table « nom normalisé -> URL du logo »,
mise en cache disque 7 jours (une requête par ligue seulement).

Fonctionnement :
  - sans FOOTBALL_DATA_KEY, le fournisseur est inactif (aucun logo, aucune erreur) ;
  - la résolution du nom passe par : correspondance exacte normalisée, puis
    alias connus (team_mapping), puis similarité floue ;
  - `enrich(match)` ajoute `home_logo` / `away_logo` à un match.

Les URL sont servies par le CDN de Football-Data.org : les images sont chargées
directement par le navigateur, sans passer par notre backend.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import time
from datetime import date

import requests

from backend.team_mapping import aliases_for, normalize_name
from backend.wikimedia_logos import get_provider as get_wikimedia_provider

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

# Codes Football-Data.co.uk -> compétitions football-data.org
LEAGUE_CODES: dict[str, str] = {
    "E0": "PL",
    "E1": "ELC",
    "F1": "FL1",
    "D1": "BL1",
    "I1": "SA",
    "SP1": "PD",
    "P1": "PPL",
    "N1": "DED",
    "B1": "B1",
    "T1": "TR",
    "SC0": "SCO",
    "G1": "GRE",
    "T2": "TR2",
}

# Codes championnat -> pays sur football-logos.cc (pour construction d'URL de secours)
FOOTBALL_LOGOS_COUNTRIES: dict[str, str] = {
    "E0": "england", "E1": "england",
    "F1": "france", "F2": "france",
    "D1": "germany", "D2": "germany",
    "I1": "italy", "I2": "italy",
    "SP1": "spain", "SP2": "spain",
    "P1": "portugal", "P2": "portugal",
    "N1": "netherlands",
    "B1": "belgium",
    "T1": "turkey",
    "SC0": "scotland",
    "G1": "greece",
    "T2": "turkey",
}

# Mapping explicite des logos de clubs de Ligue 2 (France) vers football-logos.cc
# Ces URLs contiennent le hash unique requis par le CDN du site.
CLUB_LOGO_URLS: dict[str, str] = {
    "annecy": "https://assets.football-logos.cc/logos/france/700x700/annecy.ab76c4fd.png",
    "as-saint-etienne": "https://assets.football-logos.cc/logos/france/700x700/as-saint-etienne.7db0202f.png",
    "boulogne": "https://assets.football-logos.cc/logos/france/700x700/boulogne.7f7c6c66.png",
    "clermont-foot": "https://assets.football-logos.cc/logos/france/700x700/clermont-foot.1127f5ab.png",
    "dijon": "https://assets.football-logos.cc/logos/france/700x700/dijon.85c77ca1.png",
    "dunkerque": "https://assets.football-logos.cc/logos/france/700x700/dunkerque.0612c2e9.png",
    "fc-metz": "https://assets.football-logos.cc/logos/france/700x700/fc-metz.32e4cd92.png",
    "grenoble-foot-38": "https://assets.football-logos.cc/logos/france/700x700/grenoble-foot-38.f7fb1255.png",
    "guingamp": "https://assets.football-logos.cc/logos/france/700x700/guingamp.2a1deabe.png",
    "montpellier": "https://assets.football-logos.cc/logos/france/700x700/montpellier.5ee70e10.png",
    "nancy": "https://assets.football-logos.cc/logos/france/700x700/nancy.547eae9f.png",
    "nantes": "https://assets.football-logos.cc/logos/france/700x700/nantes.c9ad5637.png",
    "pau": "https://assets.football-logos.cc/logos/france/700x700/pau.c0fccc45.png",
    "red-star-fc": "https://assets.football-logos.cc/logos/france/700x700/red-star-fc.de868140.png",
    "rodez-af": "https://assets.football-logos.cc/logos/france/700x700/rodez-af.10add4b3.png",
    "sochaux": "https://assets.football-logos.cc/logos/france/700x700/sochaux.77786db6.png",
    "stade-de-reims": "https://assets.football-logos.cc/logos/france/700x700/stade-de-reims.5276b3bc.png",
    "stade-lavallois": "https://assets.football-logos.cc/logos/france/700x700/stade-lavallois.7ffcc68c.png",
    # --- Clubs de Segunda División (Espagne) ---
    "albacete": "https://assets.football-logos.cc/logos/spain/700x700/albacete.cecf177b.png",
    "almeria": "https://assets.football-logos.cc/logos/spain/700x700/almeria.52de5c43.png",
    "burgos": "https://assets.football-logos.cc/logos/spain/700x700/burgos.7ba4a05c.png",
    "cadiz": "https://assets.football-logos.cc/logos/spain/700x700/cadiz.301f5df2.png",
    "castellon": "https://assets.football-logos.cc/logos/spain/700x700/castellon.79bbac13.png",
    "ceuta": "https://assets.football-logos.cc/logos/spain/700x700/ceuta.a195364b.png",
    "cordoba": "https://assets.football-logos.cc/logos/spain/700x700/cordoba.5f96fa9d.png",
    "eibar": "https://assets.football-logos.cc/logos/spain/700x700/eibar.991c5ffa.png",
    "eldense": "https://assets.football-logos.cc/logos/spain/700x700/eldense.2505968b.png",
    "fc-andorra": "https://assets.football-logos.cc/logos/spain/700x700/fc-andorra.76cc0487.png",
    "girona": "https://assets.football-logos.cc/logos/spain/700x700/girona.bd4a7faa.png",
    "granada": "https://assets.football-logos.cc/logos/spain/700x700/granada.d3a66ec5.png",
    "las-palmas": "https://assets.football-logos.cc/logos/spain/700x700/las-palmas.1772a616.png",
    "leganes": "https://assets.football-logos.cc/logos/spain/700x700/leganes.4cbb7429.png",
    "mallorca": "https://assets.football-logos.cc/logos/spain/700x700/mallorca.5c8d8dfe.png",
    "oviedo": "https://assets.football-logos.cc/logos/spain/700x700/oviedo.f158f5bd.png",
    "sabadell": "https://assets.football-logos.cc/logos/spain/700x700/sabadell.a42318da.png",
    "sporting-gijon": "https://assets.football-logos.cc/logos/spain/700x700/sporting-gijon.0f1df40f.png",
    "tenerife": "https://assets.football-logos.cc/logos/spain/700x700/tenerife.a8c9cf24.png",
    "valladolid": "https://assets.football-logos.cc/logos/spain/700x700/valladolid.1aca82aa.png",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "data", "logos")
CACHE_TTL_SECONDS = 7 * 24 * 3600
TIMEOUT = 20


def _season_year() -> int:
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


class LogoProvider:
    def __init__(self, api_key: str | None = None, timeout: int = TIMEOUT):
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self._memory: dict[str, dict[str, str]] = {}
        self._fallback_memory: dict[str, dict[str, str]] = {}

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Chaîne de secours : Highlightly puis API-Football
    # ------------------------------------------------------------------
    @staticmethod
    def _fallback_cache_path(source: str, league_code: str) -> str:
        return os.path.join(CACHE_DIR, f"{source}_{league_code}.json")

    def _read_fallback(self, source: str, league_code: str) -> dict[str, str] | None:
        path = self._fallback_cache_path(source, league_code)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            mapping = payload.get("mapping") or {}
            return mapping if isinstance(mapping, dict) and mapping else None
        except Exception:
            return None

    def _write_fallback(self, source: str, league_code: str, mapping: dict[str, str]) -> None:
        if not mapping:
            return
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = self._fallback_cache_path(source, league_code)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"mapping": mapping}, handle, ensure_ascii=False)
        os.replace(tmp, path)

    def _highlightly_mapping(self, league_code: str) -> dict[str, str]:
        cached = self._read_fallback("hl", league_code)
        if cached is not None:
            return cached
        key = os.environ.get("HIGHLIGHTLY_API_KEY", "").strip()
        if not key:
            return {}
        from backend.context_provider import HIGHLIGHTLY_LEAGUES

        league = HIGHLIGHTLY_LEAGUES.get(league_code)
        if not league:
            return {}
        league_name, country = league
        try:
            response = requests.get(
                "https://soccer.highlightly.net/teams",
                params={"leagueName": league_name, "countryName": country, "limit": 100},
                headers={"x-rapidapi-key": key},
                timeout=self.timeout,
            )
            if response.status_code == 429:
                return {}
            response.raise_for_status()
            teams = response.json().get("data") or []
        except Exception:
            return {}

        mapping: dict[str, str] = {}
        for team in teams:
            logo = team.get("logo")
            name = team.get("name")
            if logo and name:
                mapping[normalize_name(str(name))] = str(logo)
        self._write_fallback("hl", league_code, mapping)
        return mapping

    def _api_football_mapping(self, league_code: str) -> dict[str, str]:
        cached = self._read_fallback("af", league_code)
        if cached is not None:
            return cached
        key = os.environ.get("API_FOOTBALL_KEY", "").strip()
        if not key:
            return {}
        from backend.context_provider import LEAGUE_IDS

        league_id = LEAGUE_IDS.get(league_code)
        if not league_id:
            return {}
        try:
            response = requests.get(
                "https://v3.football.api-sports.io/teams",
                params={"league": league_id, "season": 2024},
                headers={"x-apisports-key": key},
                timeout=self.timeout,
            )
            if response.status_code == 429:
                return {}
            response.raise_for_status()
            teams = response.json().get("response") or []
        except Exception:
            return {}

        mapping: dict[str, str] = {}
        for item in teams:
            team = item.get("team") or {}
            logo = team.get("logo")
            name = team.get("name")
            if logo and name:
                mapping[normalize_name(str(name))] = str(logo)
        self._write_fallback("af", league_code, mapping)
        return mapping

    def fallback_mapping(self, league_code: str) -> dict[str, str]:
        """Logos de secours (Highlightly puis API-Football), en cache mémoire disque."""
        code = (league_code or "").strip().upper()
        if code in self._fallback_memory:
            return self._fallback_memory[code]

        merged: dict[str, str] = {}
        merged.update(self._highlightly_mapping(code))
        for key, value in self._api_football_mapping(code).items():
            merged.setdefault(key, value)
        self._fallback_memory[code] = merged
        return merged

    def _cache_path(self, league_code: str) -> str:
        return os.path.join(CACHE_DIR, f"{league_code}.json")

    def _load_from_disk(self, league_code: str) -> dict[str, str] | None:
        path = self._cache_path(league_code)
        if not os.path.exists(path):
            return None
        if (time.time() - os.path.getmtime(path)) > CACHE_TTL_SECONDS:
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            mapping = payload.get("mapping") or {}
            return mapping if isinstance(mapping, dict) else None
        except Exception:
            return None

    def _football_logos_url(self, league_code: str, club_name: str) -> str | None:
        """Construit une URL vers football-logos.cc pour un club.

        Consulte d'abord le mapping explicite des clubs connus (Ligue 2, etc.),
        puis construit une URL par défaut si le club n'est pas référencé.
        """
        country = FOOTBALL_LOGOS_COUNTRIES.get(league_code)
        if not country or not club_name:
            return None
        # 1. Vérifier le mapping explicite des clubs connus
        normalized = normalize_name(club_name)
        if normalized in CLUB_LOGO_URLS:
            return CLUB_LOGO_URLS[normalized]
        # 2. Construire une URL par défaut (sans hash, peut ne pas fonctionner)
        slug = re.sub(r"[^a-z0-9]+", "-", club_name.lower().strip()).strip("-")
        if not slug:
            return None
        return f"https://assets.football-logos.cc/logos/{country}/256x256/{slug}.png"

    def _download(self, league_code: str) -> dict[str, str] | None:
        competition = LEAGUE_CODES.get(league_code)
        if not competition:
            return None
        try:
            response = requests.get(
                f"{FOOTBALL_DATA_BASE}/competitions/{competition}/teams",
                params={"season": _season_year()},
                headers={"X-Auth-Token": self.api_key},
                timeout=self.timeout,
            )
            response.raise_for_status()
            teams = response.json().get("teams") or []
        except Exception:
            # Repli sur un cache périmé s'il existe
            path = self._cache_path(league_code)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        return (json.load(handle).get("mapping") or {}) or None
                except Exception:
                    return None
            return None

        mapping: dict[str, str] = {}
        for team in teams:
            crest = team.get("crest")
            if not crest:
                continue
            for key in ("name", "shortName", "tla"):
                value = team.get(key)
                if not value:
                    continue
                normalized = normalize_name(str(value))
                if normalized:
                    mapping.setdefault(normalized, crest)

        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = f"{self._cache_path(league_code)}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(
                {"season": _season_year(), "mapping": mapping},
                handle,
                ensure_ascii=False,
            )
        os.replace(tmp, self._cache_path(league_code))
        return mapping

    def mapping_for(self, league_code: str) -> dict[str, str]:
        """Table nom normalisé -> URL de crest pour un championnat (cache)."""
        code = (league_code or "").strip().upper()
        if not self.available or code not in LEAGUE_CODES:
            return {}
        if code in self._memory:
            return self._memory[code]

        mapping = self._load_from_disk(code)
        if mapping is None:
            mapping = self._download(code) or {}
        self._memory[code] = mapping
        return mapping

    @staticmethod
    def _lookup(mapping: dict[str, str], team_name: str, league_code: str) -> str | None:
        if not mapping or not team_name:
            return None
        normalized = normalize_name(team_name)
        if normalized in mapping:
            return mapping[normalized]

        for alias in aliases_for(team_name, league_code):
            alias_norm = normalize_name(alias)
            if alias_norm in mapping:
                return mapping[alias_norm]

        close = difflib.get_close_matches(normalized, list(mapping.keys()), n=1, cutoff=0.6)
        if close:
            return mapping[close[0]]
        return None

    def logo_for(self, team_name: str, league_code: str) -> str | None:
        """URL du logo : crest Football-Data.org, puis secours (Highlightly/API-Football/Wikimedia/football-logos.cc)."""
        code = (league_code or "").strip().upper()
        crest = self._lookup(self.mapping_for(code), team_name, code)
        if crest:
            return crest
        fb = self._lookup(self.fallback_mapping(code), team_name, code)
        if fb:
            return fb
        # Dernier recours : Wikimedia Commons (gratuit, sans clé)
        wm = get_wikimedia_provider().logo_for(team_name, code)
        if wm:
            return wm
        # Dernier recours : construction d'une URL football-logos.cc (sans clé)
        return self._football_logos_url(code, team_name)

    def enrich(self, match: dict) -> dict:
        """Ajoute `home_logo` / `away_logo` à un match (sans lever d'exception)."""
        if not isinstance(match, dict):
            return match
        league_code = str(match.get("league_code") or "").strip().upper()
        if not league_code:
            return match
        try:
            if match.get("home_logo") is None:
                match["home_logo"] = self.logo_for(match.get("home_team", ""), league_code)
            if match.get("away_logo") is None:
                match["away_logo"] = self.logo_for(match.get("away_team", ""), league_code)
        except Exception:
            pass
        return match


_provider: LogoProvider | None = None


def get_provider() -> LogoProvider:
    """Provider singleton configuré via FOOTBALL_DATA_KEY."""
    global _provider
    if _provider is None:
        _provider = LogoProvider(os.environ.get("FOOTBALL_DATA_KEY", ""))
    return _provider
