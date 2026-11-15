"""
backend/api.py - API REST Foot Predict (Phase 3)

Lancement local :
    uvicorn backend.api:app --reload --port 8000
    (ou, depuis backend/ : uvicorn api:app --reload --port 8000)

Endpoints :
    GET /api/health                    état du service et du modèle
    GET /api/leagues                   les 5 championnats suivis
    GET /api/matches/upcoming          affiches + prédictions (filtres)
    GET /api/matches/{match_id}        analyse détaillée d'un match
    GET /api/backtest/stats            KPIs et courbe de bankroll (Phase 2)
    GET /api/backtest/bets             historique paginé des paris simulés

Documentation interactive : http://localhost:8000/docs
"""

from __future__ import annotations

import os
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# --- Bootstrap des imports racine (config.py, prediction_engine.py, ...) ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.env import load_dotenv  # noqa: E402

# Charge .env avant toute lecture d'ALLOWED_ORIGINS / API_FOOTBALL_KEY / ODDS_API_KEY.
load_dotenv()

from backend.service import LEAGUE_META, MARKET_LABELS, service  # noqa: E402

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001",
    ).split(",")
    if origin.strip()
]


def _warmup():
    """Préchauffe le modèle en arrière-plan (évite un premier appel trop lent)."""
    try:
        service.ensure_model()
        service.ensure_fixtures()
        cache = service.predictions_cache_info()
        print(
            "[API] Modèle et affiches prêts. Cache prédictions : "
            f"{cache['count']} matchs (source={cache['source']}, généré={cache['generated_at']})."
        )
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        print(f"[API] Préchauffage impossible : {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warmup, daemon=True).start()
    yield


app = FastAPI(
    title="Foot Predict API",
    description=(
        "API de prédictions football (1X2, Over/Under 2.5, BTTS, Value Bets) "
        "sur les 5 grands championnats européens."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Racine / santé
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/health", tags=["Système"])
def health():
    """Vérifie que l'API répond et indique si le modèle est chargé."""
    info = {"status": "ok", "model_ready": service.model_ready}
    if service.model_ready:
        try:
            info.update(service.model_info())
        except Exception as exc:
            info["status"] = "degraded"
            info["error"] = str(exc)
    try:
        info["predictions"] = service.predictions_cache_info()
    except Exception as exc:
        info["predictions"] = {"error": str(exc)}
    return info


@app.get("/api/leagues", tags=["Référentiel"])
def leagues():
    """Liste des championnats supportés (utilisée par les filtres du frontend)."""
    return {
        "leagues": [
            {
                "code": code,
                "name": meta["name"],
                "country": meta["country"],
                "logo": service.league_logo(code),
            }
            for code, meta in LEAGUE_META.items()
        ],
        "value_threshold": 5.0,
        "markets": MARKET_LABELS,
    }


# ---------------------------------------------------------------------------
# Matchs
# ---------------------------------------------------------------------------
@app.get("/api/matches/upcoming", tags=["Matchs"])
def upcoming_matches(
    league: str | None = Query(
        default=None,
        description="Code championnat : E0, F1, D1, I1 ou SP1.",
    ),
    value_only: bool = Query(
        default=False,
        description="Ne renvoyer que les matchs présentant au moins un value bet.",
    ),
):
    """
    Prochaines affiches enrichies par le moteur :
    probabilités 1X2 / Over 2.5 / BTTS, top 3 scores, cotes bookmaker,
    cote juste et indicateur de value bet (EV > 5 %).

    Les prédictions sont lues depuis data/upcoming_predictions.json
    (généré par backend/update_pipeline.py) ; si ce fichier est absent,
    elles sont recalculées à la volée à partir des fixtures.
    """
    if league and league.strip().upper() not in LEAGUE_META:
        raise HTTPException(
            status_code=422,
            detail=f"Championnat inconnu : {league}. Valeurs acceptées : {list(LEAGUE_META)}",
        )
    try:
        return service.get_upcoming(league=league, value_only=value_only)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/matches/{match_id}", tags=["Matchs"])
def match_detail(match_id: str):
    """
    Analyse détaillée d'un match :
      - matrice de probabilités des scores exacts (0-0 à 5-5) ;
      - évolution du score Elo des deux équipes ;
      - statistiques des 5 derniers matchs ;
      - indices d'attaque/défense et paramètres du simulateur de Kelly.
    """
    try:
        match = service.get_match(match_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if match is None:
        raise HTTPException(
            status_code=404,
            detail="Match introuvable. Les affiches sont rafraîchies périodiquement : "
                   "rechargez la liste des matchs.",
        )
    return match


# ---------------------------------------------------------------------------
# Historique : pronostics vs résultats
# ---------------------------------------------------------------------------
@app.get("/api/history/matchdays", tags=["Historique"])
def history_matchdays(
    league: str = Query(description="Code championnat : E0, F1, D1, I1 ou SP1."),
    limit: int = Query(default=6, ge=1, le=15, description="Nombre de journées à reconstruire."),
):
    """
    Liste des dernières journées d'un championnat, avec pour chacune :
    nombre de matchs, précision du pronostic 1X2 et Brier Score moyen.

    Les prédictions sont reconstruites dans l'ordre chronologique, sans fuite de
    données : tous les matchs d'une journée sont prédits avant l'injection des
    résultats de cette journée.
    """
    code = league.strip().upper()
    if code not in LEAGUE_META:
        raise HTTPException(
            status_code=422,
            detail=f"Championnat inconnu : {league}. Valeurs acceptées : {list(LEAGUE_META)}",
        )
    payload = service.history_matchdays(code, limit)
    return {
        "league": payload["league"],
        "league_name": payload["league_name"],
        "limit": payload["limit"],
        "generated_at": payload["generated_at"],
        "matchdays": [
            {
                "date": matchday["date"],
                "date_from": matchday["date_from"],
                "date_to": matchday["date_to"],
                "label": matchday["label"],
                "summary": matchday["summary"],
            }
            for matchday in payload["matchdays"]
        ],
    }


@app.get("/api/history/matchday", tags=["Historique"])
def history_matchday(
    league: str = Query(description="Code championnat : E0, F1, D1, I1 ou SP1."),
    date: str = Query(description="Date de la journée (YYYY-MM-DD)."),
    limit: int = Query(default=6, ge=1, le=15),
):
    """Détail d'une journée : pronostics, résultats réels, Brier et cotes/EV."""
    code = league.strip().upper()
    if code not in LEAGUE_META:
        raise HTTPException(
            status_code=422,
            detail=f"Championnat inconnu : {league}. Valeurs acceptées : {list(LEAGUE_META)}",
        )
    payload = service.history_matchdays(code, limit)
    for matchday in payload["matchdays"]:
        if matchday["date"] == date:
            return matchday
    raise HTTPException(
        status_code=404,
        detail=f"Journée {date} introuvable pour {code}. "
               "Vérifiez la liste via /api/history/matchdays.",
    )


# ---------------------------------------------------------------------------
# Backtesting / transparence
# ---------------------------------------------------------------------------
@app.get("/api/backtest/stats", tags=["Transparence"])
def backtest_stats():
    """
    Statistiques du backtesting Phase 2 : ROI et profit (flat / Quarter-Kelly),
    Brier Score modèle vs bookmaker, répartition par championnat et par marché,
    et courbe d'évolution de la bankroll.
    """
    try:
        return service.backtest_stats()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Exports de backtest indisponibles. Lancez `python run_backtest.py`.",
        ) from exc


@app.get("/api/backtest/bets", tags=["Transparence"])
def backtest_bets(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    league: str | None = Query(default=None, description="Filtre texte sur le championnat."),
    market: str | None = Query(default=None, description="Home, Draw ou Away."),
):
    """Historique paginé des paris simulés (alimente le tableau de transparence)."""
    return service.backtest_bets(limit=limit, offset=offset, league=league, market=market)
