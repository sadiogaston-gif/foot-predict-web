"""
backend/env.py - Chargement minimal du fichier .env (sans dépendance externe).

Permet à l'API FastAPI et au pipeline d'automatisation de lire les variables
d'environnement locales (clés API, options) sans installer python-dotenv.
Les variables déjà définies dans l'environnement du processus sont prioritaires.
"""

from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv(path: str | None = None) -> None:
    """Charge les paires CLÉ=VALEUR du fichier .env (si présentes)."""
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
    except OSError:
        pass
