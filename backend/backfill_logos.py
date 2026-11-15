"""
backend/backfill_logos.py - Pré-remplit les caches de logos.

Les logos proviennent d'abord des crests Football-Data.org (compétitions
disponibles sur le plan gratuit), puis de Highlightly et d'API-Football pour les
clubs non couverts (notamment les deuxièmes divisions).

Ce script force le téléchargement et la mise en cache des tables de secours.
À relancer après réinitialisation des quotas (API-Football : 100 requêtes/jour,
Highlightly : limite journalière).

Usage :
    python -m backend.backfill_logos
"""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.env import load_dotenv  # noqa: E402

load_dotenv()

from backend.logos import get_provider  # noqa: E402
from config import LEAGUES  # noqa: E402


def main() -> int:
    provider = get_provider()
    print(
        "Sources configurées :",
        "Football-Data.org" if provider.available else "—",
        "| Highlightly"
        if os.environ.get("HIGHLIGHTLY_API_KEY")
        else "",
        "| API-Football" if os.environ.get("API_FOOTBALL_KEY") else "",
    )

    total = 0
    for name, info in LEAGUES.items():
        code = info["code"]
        crests = provider.mapping_for(code)
        fallback = provider.fallback_mapping(code)
        total += len(fallback)
        print(f"{code:4} {name:38} crests={len(crests):3} secours={len(fallback):3}")
        time.sleep(1)

    print(f"\nLogos de secours en cache : {total}")
    if total == 0:
        print(
            "Aucun logo de secours récupéré (quota atteint ou sources indisponibles). "
            "Réessayez plus tard ; les caches seront alors remplis automatiquement."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
