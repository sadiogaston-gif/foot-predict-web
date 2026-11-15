# Foot Predict — Phases 1, 2, 3, 3.5 & 4

Plateforme d'analyse et de prédiction football (1X2, Over/Under 2.5, BTTS,
Value Bets) basée sur les données gratuites de Football-Data.co.uk, pour les
13 championnats (première et deuxième divisions) de 7 pays européens.

> **État actuel** : moteur mathématique (Phase 1), backtesting walk-forward
> sans fuite de données (Phase 2) et plateforme Full-Stack API + Web (Phase 3)
> sont en place et validés de bout en bout. L'alimentation des affiches est
> désormais **hybride** : Football-Data.co.uk pour l'entraînement, The Odds API
> pour les matchs à venir et les cotes en temps réel.

## Résultats clés — protocole Phase 2 (saison 2025-26)

Warm-up complet 2024-25, paris simulés sur 2025-26 uniquement (1 752 matchs),
filtre du cahier des charges : **EV > 5 %** et **cotes 1,40–5,00**.

| Indicateur | Valeur |
|---|---|
| Brier Score modèle | **0,6018** |
| Brier Score bookmaker (dé-marginé) | 0,5827 |
| Brier Score fréquences de base | 0,6491 |
| Précision 1X2 | 51,26 % |
| Paris simulés | 928 |
| Taux de réussite | 35,02 % |
| Cote moyenne jouée | 2,905 |
| ROI stratégie A (flat 1 u) | **−7,74 %** |
| ROI stratégie B (Quarter-Kelly) | **−11,25 %** |

Conclusion : le modèle apporte une information réelle (il bat les fréquences de
base) mais **ne bat pas le marché** ; aucun avantage de paris n'est démontré.
Détails : [RESULTS.md](RESULTS.md).

## Phase 3 — Architecture Full-Stack

Le projet est découpé en deux applications distinctes :

```
FOOT_PREDICT/
├── backend/          # API REST FastAPI (Phase 3)
├── frontend/         # Next.js 15 + Tailwind CSS + Recharts (Phase 3)
├── config.py         # …
├── data_loader.py    # …
├── prediction_engine.py  # …
├── backtest.py       # …
├── main.py / run_backtest.py / tune_*.py
├── data/             # …
└── models/
```

### Backend — FastAPI (`backend/`)

Fichiers : `backend/api.py` (endpoints), `backend/service.py` (couche métier,
singleton thread-safe).

Lancement local :

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.api:app --reload --port 8000
```

- Swagger / ReDoc : http://localhost:8000/docs
- Health : `GET /api/health`

Endpoints :

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/health` | État du service et du modèle |
| GET | `/api/leagues` | Championnats supportés + seuil de value |
| GET | `/api/matches/upcoming` | Affiches + prédictions (`?league=E0\|F1\|D1\|I1\|SP1`, `?value_only=true`) |
| GET | `/api/matches/{match_id}` | Analyse détaillée (matrice de scores, Elo, forme, forces, Kelly) |
| GET | `/api/history/matchdays` | Journées passées + précision / Brier (`?league=E0&limit=6`) |
| GET | `/api/history/matchday` | Détail d'une journée : pronostics vs résultats (`?league=E0&date=YYYY-MM-DD&limit=6`) |
| GET | `/api/backtest/stats` | KPIs backtesting + courbe de bankroll |
| GET | `/api/backtest/bets` | Historique paginé des paris simulés (`?limit=`, `?offset=`, `?league=`, `?market=`) |

La couche `backend/service.py` :

- entraîne une seule fois le `PredictionEngine` (singleton) sur les données
  historiques (cache `data/raw`) ;
- sert `GET /api/matches/upcoming` **directement depuis
  `data/upcoming_predictions.json`** (cache pré-calculé par le pipeline : réponse
  en quelques millisecondes, sans recalcul ni appel réseau) ;
- en repli, si ce fichier est absent, recalcule à la volée depuis
  `data/fixtures.csv` (cache disque, rafraîchissement 30 min, reprojection si
  snapshot figé) ;
- expose uniquement des types JSON sûrs (aucun type numpy ne sort du module) ;
- lit les exports Phase 2 (`data/backtest_results.csv`, `data/backtest_report.json`).

CORS : configurable via la variable d'environnement `ALLOWED_ORIGINS`
(valeurs par défaut : `http://localhost:3000,http://127.0.0.1:3000`).

### Frontend — Next.js (`frontend/`)

Pages :

- `/` — « Matchs & Value Bets » : filtres championnat + interrupteur
  « Value bets uniquement », cartes de matchs (barre de probabilités 1/X/2,
  cote marché vs cote juste, badge `VALUE +X%`).
- `/match/[id]` — Détail : comparaison Elo + indices attaque/défense, heatmap des
  probabilités de scores (0-0 à 5-5), évolution Elo, forme sur 5 derniers matchs,
  simulateur de mise (Kelly fractionné), tableau des value bets.
- `/history` — **Journées passées** : sélection du championnat et de la journée,
  comparaison pronostic vs résultat réel, précision, Brier et value bets.
- `/performance` — KPIs backtesting (ROI flat / Quarter-Kelly, Brier Score vs
  bookmaker, log-loss, précision), courbe de bankroll (recharts), tableaux par
  championnat et par type de pari.

Composants principaux : `HomeView`, `MatchCard`, `ProbabilityBar`, `ValueBadge`,
`ScoreHeatmap`, `EloChart`, `FormTable`, `KellySimulator`, `BankrollChart`,
`KpiCard`, `PerformanceView`, `MatchDetailView`, `HistoryView`,
`CountryLeagueFilter`, `Navbar`, `Footer`.

### Filtre par pays et deuxièmes divisions

L'interface propose deux niveaux de filtre : **pays** (Angleterre, France,
Allemagne, Italie, Espagne, Portugal, Pays-Bas), puis **championnat** (première
ou deuxième division). Le référentiel partagé est dans
[`frontend/lib/leagues.ts`](frontend/lib/leagues.ts) ; l'API expose le même
référentiel via `GET /api/leagues` (avec le pays).

Deuxièmes divisions disponibles : Championship (`E1`), Ligue 2 (`F2`),
2. Bundesliga (`D2`), Serie B (`I2`), Segunda División (`SP2`), Liga Portugal 2
(`P2`). La deuxième division néerlandaise (Eerste Divisie) n'est **pas publiée**
par Football-Data : elle n'est donc pas disponible.

Affiches des deuxièmes divisions : OpenFootball ne fournit que la Championship
(`en.2.json`). Les autres n'ont pas de calendrier libre, mais peuvent recevoir
des cotes via `fixtures.csv` — c'est le cas de la Segunda División, qui génère
déjà des value bets.

### Logos des clubs et drapeaux

**Drapeaux** : chaque pays du filtre affiche son drapeau via [flagcdn](https://flagcdn.com)
(libres d'usage) : Angleterre, France, Allemagne, Italie, Espagne, Portugal,
Pays-Bas.

**Logos** : chaîne de sources, du plus fiable au plus généraliste —

1. **crest Football-Data.org** (compétitions du plan gratuit : PL, FL1, BL1, SA,
   PD, PPL, DED, ELC) ;
2. **Highlightly** (`/teams`, plan BASIC) pour les clubs non couverts ;
3. **API-Football** (`/teams?league=…&season=2024`) en dernier recours.

Les tables sont mises en cache disque (`data/logos/`, 7 à 30 jours) : une requête
par championnat, pas par visite. Le script
[`backend/backfill_logos.py`](backend/backfill_logos.py) force le remplissage :

```bash
python -m backend.backfill_logos
```

**Logos des championnats** : les emblèmes proviennent de Football-Data.org
(`/v4/competitions`, cache disque 30 jours) pour les 8 compétitions du plan
gratuit (PL, ELC, FL1, BL1, SA, PD, PPL, DED). Les 5 deuxièmes divisions non
couvertes (F2, D2, I2, SP2, P2) affichent un badge généré (code + couleur). Les
logos apparaissent dans le sélecteur de championnat, sur les cartes de matchs et
dans l'en-tête de la fiche ; `GET /api/leagues` expose le champ `logo`.

**Badge généré** : si aucun logo n'est disponible (quota épuisé, club absent des
sources), l'interface affiche un badge déterministe avec les initiales du club et
une teinte propre — chaque club garde donc une identité visuelle.

> Quotas à connaître : API-Football gratuit = 100 requêtes/jour (les fixtures
> 2026-27 sont par ailleurs bloquées) ; Highlightly a une limite journalière.
> Une fois les quotas réinitialisés, relancer le backfill remplit les logos
> manquants (notamment les deuxièmes divisions hors Championship).

### Historique des journées (pronostics vs résultats)

[`backend/history.py`](backend/history.py) reconstruit les dernières journées de
chaque championnat en parcourant les matchs dans l'ordre chronologique :

- **aucune fuite de données** : tous les matchs d'une date sont prédits avant que
  le moindre résultat de cette date soit injecté dans le moteur ;
- une « journée » regroupe les dates d'un même week-end (vendredi → dimanche) ;
- pour chaque match : probabilités 1X2, pronostic, score réel, juste/manqué,
  Brier Score, cotes Bet365 (ou moyenne du marché) et EV ;
- synthèse par journée : précision, Brier moyen, value bets détectés/gagnés.

Les résultats sont mis en cache mémoire et disque (`data/history/`), invalidés
automatiquement lorsque les CSV historiques changent.

Lançé avec :

```bash
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
```

Build de production :

```bash
cd frontend && npm run build && npm start
```

Le frontend consomme l'API via `frontend/lib/api.ts` (`apiGet`), configurable
via `NEXT_PUBLIC_API_URL`.

### Lancement complet (local)

**En un clic (Windows)** : double-cliquez sur [`start_all.bat`](start_all.bat).
Deux fenêtres s'ouvrent (backend sur 8011, frontend sur 3000) ; fermez-les pour
arrêter l'application.

**En ligne de commande** :

```bash
# 1) Backend (terminal 1)
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8011

# 2) Frontend (terminal 2)
cd frontend && npm run dev
```

- Frontend : http://localhost:3000
- Backend : http://127.0.0.1:8011/docs

Le frontend lit l'URL de l'API dans `frontend/.env.local`. Par défaut
`NEXT_PUBLIC_API_URL` est **vide** : le navigateur appelle l'API sur sa propre
origine (`/api/...`) et Next.js proxifie ces requêtes vers le backend indiqué par
`API_PROXY_TARGET` (voir `rewrites` dans `frontend/next.config.mjs`). Aucun
problème de CORS ni de port n'est donc possible côté navigateur.

En production, deux options :

- définir `NEXT_PUBLIC_API_URL=https://<backend>` pour appeler Render directement ;
- ou définir `API_PROXY_TARGET=https://<backend>` sur le serveur Next.js (Vercel)
  pour conserver le proxy same-origin.

`frontend/.env.local` est ignoré par git : en production, les variables sont
fournies par Vercel.

> **Ports alternatifs** : si `WinError 10013` ou `10048` apparaît (port réservé ou
> déjà utilisé par un ancien processus), choisissez un autre port (8011, 8020…)
> dans `start_backend.bat` et reportez-le dans `frontend/.env.local`, puis
> redémarrez les deux serveurs.

### Déploiement

- **Backend** → [Render](https://render.com) : service Python, start command
  `uvicorn backend.api:app --host 0.0.0.0 --port $PORT`, build
  `pip install -r backend/requirements.txt`, variable d'environnement
  `ALLOWED_ORIGINS=https://<frontend-url>`.
- **Frontend** → [Vercel](https://vercel.com) : Root Directory `frontend`,
  build `npm run build`, start `npm start`, variable
  `NEXT_PUBLIC_API_URL=https://<backend-url>`.

## Arborescence

```
FOOT_PREDICT/
├── config.py              # Ligues, saisons, hyperparamètres, filtres de mise
├── data_loader.py         # Téléchargement + nettoyage des CSV
├── prediction_engine.py   # Elo dynamique, Time Decay, Poisson/Dixon-Coles
├── calibration.py         # Calibration isotonique 1X2 (PAVA, sans dépendance)
├── evaluate_models.py     # Comparaison calibration / pooled vs par ligue
├── evaluate_xg.py         # Comparaison forces sur buts vs xG (2026-27)
├── backtest.py            # Backtesting walk-forward + métriques
├── backend/               # API REST FastAPI (Phase 3)
│   ├── api.py             # Endpoints REST
│   ├── service.py         # Couche métier / singleton
│   ├── team_mapping.py    # Noms The Odds API -> noms Football-Data (+ fuzzy)
│   ├── team_context.py    # Forme enrichie (10 matchs, splits, séries, repos)
│   ├── context_provider.py# Contexte externe optionnel (API-Football)
│   ├── logos.py           # Écussons (FD.org, Highlightly, API-Football) + badges
│   ├── league_logos.py    # Emblèmes des championnats (Football-Data.org)
│   ├── backfill_logos.py  # Pré-remplissage des caches de logos
│   ├── fixtures_openfootball.py # Calendrier libre sans clé API
│   ├── update_pipeline.py # Pipeline d'automatisation (fusion des sources)
│   └── requirements.txt
├── frontend/              # Next.js + Tailwind + Recharts (Phase 3)
│   ├── app/               # pages : /, /match/[id], /performance
│   ├── components/        # Vues et widgets UI
│   ├── lib/               # client API + types + format
│   └── .env.example       # NEXT_PUBLIC_API_URL
├── .github/
│   └── workflows/
│       └── auto_update.yml  # Auto-update predictions (Phase 3.5)
├── .env.example           # Modèle de variables d'environnement (backend)
├── render.yaml            # Blueprint Render (Phase 4)
├── main.py                # Démo Phase 1 (prédiction d'un match)
├── run_backtest.py        # Lancement du backtesting Phase 2
├── tune_model.py          # Réglage des hyperparamètres (validation/holdout)
├── tune_filters.py        # Sélection des filtres de mise + bootstrap
├── requirements.txt
├── backend/requirements.txt
├── README.md
├── RESULTS.md             # Rapport de backtesting détaillé
├── data/                  # Généré à l'exécution
│   ├── raw/               # CSV bruts Football-Data.co.uk (cache local)
│   ├── backtest_results.csv  # Historique complet des paris simulés
│   ├── backtest_report.json  # Métriques agrégées
│   ├── market_quotes.csv  # Toutes les cotes rencontrées
│   ├── model_tuning.json
│   ├── filter_selection.json
│   ├── fixtures.csv       # Affiches (Phase 3)
│   └── upcoming_predictions.json  # Cache prédictif (Phase 3.5)
└── models/
    └── elo_ratings.json
```

## Installation

Python 3.10+ :

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

Node.js 18+ et pnpm/npm :

```bash
cd frontend
npm install
```

## Utilisation

```bash
python main.py          # Phase 1 : prédiction d'un match (Arsenal vs Liverpool)
python run_backtest.py  # Phase 2 : backtest 2025-26 avec warm-up 2024-25
python -m uvicorn backend.api:app --reload --port 8000   # Phase 3 : API

cd frontend && npm run dev   # Phase 3 : interface web
```

```bash
python run_backtest.py --season 2425 --ev 0.05 --min-odds 1.40 --max-odds 5.00
python run_backtest.py --season 2627 --bankroll 100 --no-cache
python tune_model.py    # Réglage des hyperparamètres (Brier validation/holdout)
python tune_filters.py  # Sélection des filtres de mise + IC bootstrap
```

`run_backtest.py` :

- utilise `data/raw` comme cache (aucun téléchargement si les CSV sont présents ;
  `--no-cache` force la mise à jour) ;
- prend la saison précédente comme warm-up complet ;
- parie uniquement sur la saison cible ;
- affiche le bilan et écrit `data/backtest_results.csv`,
  `data/backtest_report.json` et `data/market_quotes.csv`.

`tune_filters.py` et `tune_model.py` supposent que `run_backtest.py` a déjà été
exécuté (ils lisent `data/market_quotes.csv`).

## Moteur mathématique

1. **Elo dynamique** : base 1500, mise à jour après chaque match (résultat,
   écart de buts, avantage terrain +65 points).
2. **Forces attaque/défense avec Time Decay** : décroissance exponentielle en
   ligne (`exp(-λ·jours)`), λ = 0,002/jour.
3. **Poisson ajusté (Dixon-Coles simplifié)** : matrice 0–6 × 0–6, correction ρ
   sur les scores faibles (0-0, 1-0, 0-1, 1-1).
4. **Pont Elo → buts** : facteur `exp(0,30 · Δelo/400)`, borné à ±0,35 en log.
5. **Calibration** : mélange 75 % modèle / 25 % fréquences de base observées
   (avec priors), pour corriger la sur-confiance du Poisson brut.
6. **xG** : forces attaque/défense estimées sur les Expected Goals quand ils
   sont disponibles (2026-27), avec repli sur les buts ; l'Elo reste basé sur
   les résultats réels.

### Phase 5 — calibration et modèles par championnat (mesurés)

[`evaluate_models.py`](evaluate_models.py) compare plusieurs variantes en
walk-forward strict (calibrateurs appris sur 2024-25, évalués sur 2025-26,
aucun résultat futur utilisé) :

| Variante | Brier ↓ | Log-loss ↓ |
|---|---|---|
| modèle unique, probabilités brutes | 0,6142 | 1,0334 |
| modèle unique + mélange alpha (précédent) | 0,6019 | 1,0078 |
| modèle unique + isotonique (pooled) | 0,6012 | 1,0068 |
| **un moteur par championnat + alpha** | **0,6005** | **1,0058** |
| un moteur par championnat + isotonique | 0,6051 | 1,0473 |

Décisions :

- `config.USE_PER_LEAGUE_ENGINES = True` : un moteur entraîné par championnat
  (gain mesuré, faible mais cohérent) ;
- `config.CALIBRATION_ENABLED = False` : la calibration isotonique
  ([`calibration.py`](calibration.py), PAVA sans dépendance) est implémentée et
  disponible, mais mesurée **neutre** sur le modèle unique et **néfaste**
  combinée au modèle par championnat (sur-apprentissage des courbes par ligue).

Résultats détaillés et Brier par ligue : `data/model_comparison.json`.
Pour régénérer l'analyse : `python evaluate_models.py`.

> **Constat honnête** : la calibration et le par-ligue valent ~0,0015 de Brier —
> du bruit à l'échelle d'une saison. Les **xG** (ci-dessous) apportent bien
> davantage.

### Phase 6 — Expected Goals (xG)

Les fichiers 2026-27 de Football-Data contiennent les colonnes **`HxG` / `AxG`**
(Expected Goals par match) — aucune source payante ni scraping nécessaire. Les
saisons antérieures n'en ont pas : les xG sont donc utilisés pour les matchs de
2026-27, et les buts restent le repli pour le reste de l'historique.

Principe : les **forces attaque/défense** sont estimées sur les xG (bien moins
bruités qu'un score), tandis que l'**Elo** et les **fréquences de base**
(1X2, Over 2.5) restent calculés sur les buts — les xG ne sont pas des résultats.

Évaluation walk-forward sur 2026-27 (500 matchs, warm-up 2024-25 + 2025-26) :

| Forces estimées sur | Brier ↓ | Log-loss ↓ |
|---|---|---|
| buts | 0,5728 | 0,9681 |
| **xG** | **0,5675** | **0,9611** |

Brier par ligue (buts → xG) : D1 0,599 → 0,577 · F1 0,586 → 0,577 · SP1 0,562
→ 0,559 · E0 0,618 → 0,611 · I1 0,513 → 0,522 (seule ligue en recul).

Décision : `config.USE_XG = True`. Pour régénérer l'analyse :
`python evaluate_xg.py` (résultats dans `data/xg_comparison.json`).

> Limite : l'échantillon xG ne couvre qu'une saison (~500 matchs) et les saisons
> passées n'ont pas de xG. L'effet devrait se renforcer à mesure que l'historique
> xG s'accumule ; il faudrait une source historique (Understat, payante/API)
> pour l'exploiter pleinement.

## Anti-fuite de données

Le backtesting parcourt les matchs dans l'ordre chronologique strict. Les matchs
d'une même journée sont **tous prédits avant** que le moindre résultat de cette
journée soit injecté : pour prédire un match du 15/03, le moteur ne connaît que
les rencontres **strictement antérieures au 15/03**. Les résultats du 15/03 ne
servent qu'aux journées suivantes.

La saison précédente est utilisée en entier comme warm-up (initialisation des
Elo, des forces attaque/défense et des fréquences de base). Les moyennes et
fréquences sont reconstruites match par match, jamais précalculées sur
l'ensemble du jeu de données.

## Limites connues

- Le modèle est moins bon que les cotes Bet365 (Brier 0,601 vs 0,576).
- Les forces sont estimées par championnat (moteurs séparés depuis la Phase 5).
- Pas de xG, blessures, compositions ni contexte de calendrier.
- Le ρ de Dixon-Coles est fixe, non estimé par maximum de vraisemblance.

## Phase 4 — Déploiement en production

### Backend (FastAPI) → Render

Le service backend est décrit par le blueprint [`render.yaml`](render.yaml) :

```yaml
services:
  - type: web
    name: foot-predict-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt -r backend/requirements.txt
    startCommand: uvicorn backend.api:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: PYTHON_VERSION
        value: "3.11.9"
      - key: ALLOWED_ORIGINS
        value: https://foot-predict.vercel.app
```

Déploiement : connecter le repo GitHub sur Render → « New → Blueprint » →
`render.yaml` → déployer. Le service expose `https://<service>.onrender.com`.

### Frontend (Next.js) → Vercel

- Root Directory : `frontend`
- Build command : `npm run build`
- Output : `.next`
- Variable d'environnement : `NEXT_PUBLIC_API_URL=https://<service>-api.onrender.com`

### Automatisation continue et architecture hybride (Phase 3.5)

Le fichier `fixtures.csv` de Football-Data.co.uk se fige pendant les trêves
internationales et ne contient alors que des divisions inférieures. L'alimentation
des affiches est donc hybride :

| Source | Rôle |
|---|---|
| Football-Data.co.uk (CSV de saison, `data/raw/`) | **Uniquement l'entraînement** : scores, classements Elo, forces attaque/défense |
| [The Odds API](https://the-odds-api.com/) (`/v4/sports/{sport_key}/odds`) | **Affiches + cotes 1X2** temps réel (marché `h2h`, région `eu`) — facultative |
| [OpenFootball](https://github.com/openfootball/football.json) (JSON statique) | **Calendrier libre, sans clé ni quota** : vraies dates des prochaines journées (sans cotes) |
| `data/fixtures.csv` | Affiches + cotes Bet365 quand les championnats suivis y figurent |

Les trois sources sont **fusionnées et dédupliquées** (clé : championnat +
domicile + extérieur) ; une ligne portant des cotes est toujours préférée.

**Ordre de priorité** lors de la fusion :

1. **The Odds API** — si `ODDS_API_KEY` est valide : cotes temps réel
   (Pinnacle, puis Bet365, sinon consensus du marché) ;
2. **`fixtures.csv`** — cotes Bet365 quand les championnats suivis y figurent ;
3. **OpenFootball** — complète le calendrier (dates réelles, sans cotes).

Aucune source n'est supprimée : The Odds API reste la référence dès qu'une clé
est fournie ; OpenFootball ne sert qu'à compléter les journées qu'elle ne couvre
pas (au-delà de sa fenêtre) ou à prendre le relais sans clé.

#### Données enrichies : forme, effectifs, blessures, compositions, notes

| Information | Source | Clé requise ? | Entre dans le modèle ? |
|---|---|---|---|
| **Forme enrichie** (10 derniers matchs, domicile/extérieur, clean sheets, BTTS, Over 2.5, série, jours de repos, cadence, tendance Elo) | Historique Football-Data (interne) | non | oui (Elo/forces) |
| **Effectifs** (joueurs, postes, âge, nationalité) | Football-Data.org (principal), API-Football (secours) | oui | non |
| **Classement** (position, points, forme) | Football-Data.org | oui | non |
| **Blessures / absences** | API-Football | oui | non |
| **Compositions** (formation, titulaires) | Highlightly | oui | non |
| **Notes des joueurs** (`matchRating`) | Highlightly | oui | non |

Activation du contexte externe (optionnel) — trois clés indépendantes :

1. **Football-Data.org** (`FOOTBALL_DATA_KEY`) : effectifs + classement
   (10 requêtes/min, sans quota journalier) ;
2. **Highlightly** (`HIGHLIGHTLY_API_KEY`) : compositions + notes des joueurs ;
3. **API-Football** (`API_FOOTBALL_KEY`) : blessures (et effectifs de secours),
   mode `direct`/`rapidapi` détecté automatiquement.

Ajouter les clés dans `.env`, puis redémarrer le backend. Chaque section est
dégradée indépendamment : une source absente n'empêche pas les autres de
s'afficher, et une note explique pourquoi.

**Limites des plans gratuits** (constatées en conditions réelles) :

- Football-Data.org : effectifs et classement disponibles ; 10 requêtes/minute.
- API-Football gratuit : **blessures limitées aux saisons 2022-2024**, donc pas
  de blessures sur la saison en cours (nécessite un plan payant). Quota : 10/min, 100/j.
- Highlightly (plan BASIC) : matchs, compositions et notes disponibles ;
  **pas d'endpoint blessures**.
- Compositions publiées ~1 h avant le coup d'envoi.
- Notes : celles du match à venir n'existent qu'après la rencontre ; en attendant,
  l'application affiche les **notes du dernier match joué** de chaque équipe.

**Limites assumées** : ces données ne sont pas historisées chez nous, donc elles
ne peuvent pas être backtestées et **n'entrent pas** dans le calcul des
probabilités. Les réponses sont mises en cache (effectifs 7 j, blessures 6 h,
compositions 30 min, notes 12 h) pour rester dans les quotas.

#### Mode sans aucune clé API (recommandé pour un hébergement gratuit)

Aucune inscription n'est nécessaire : il suffit de lancer

```bash
python backend/update_pipeline.py
```

Le pipeline télécharge alors :

- les CSV de saison Football-Data (entraînement) ;
- les fichiers OpenFootball `2026-27/en.1.json`, `fr.1.json`, `de.1.json`,
  `it.1.json`, `es.1.json` (calendrier complet, cache local
  `data/raw/openfootball/`, TTL 12 h) ;
- `fixtures.csv` s'il contient des affiches des championnats suivis (avec
  cotes Bet365).

Résultat typique en trêve internationale : **106 affiches à venir sur 21 jours**
(30 Premier League, 20 Serie A, 20 La Liga, 18 Bundesliga, 18 Ligue 1), avec les
vraies dates. Les prédictions (1X2, Over/Under, BTTS, scores exacts) sont
calculées normalement ; les **value bets sont indisponibles** faute de cotes
bookmaker, et l'interface l'indique dans un bandeau.

Profondeur configurable : `FIXTURES_HORIZON_DAYS=21` (en jours).

Championnats interrogés : `soccer_epl` (E0), `soccer_france_ligue_one` (F1),
`soccer_germany_bundesliga` (D1), `soccer_italy_serie_a` (I1),
`soccer_spain_la_liga` (SP1).

Le pipeline [`backend/update_pipeline.py`](backend/update_pipeline.py) exécute :

1. **Étape A** — téléchargement des CSV de la saison en cours (intégration des
   scores récents).
2. **Étape B** — récupération des affiches + cotes via The Odds API
   (`markets=h2h`, `regions=eu`), cote de référence Pinnacle puis Bet365, sinon
   moyenne du marché. Les noms d'équipes sont traduits par
   [`backend/team_mapping.py`](backend/team_mapping.py) (dictionnaire complet des
   13 championnats + recherche floue `difflib` en secours, donc aucun plantage sur
   un club promu).
3. **Étape C** — recalcul des classements Elo et des forces attaque/défense.
4. **Étape D** — génération des prédictions et écriture **atomique** dans
   `data/upcoming_predictions.json`.

**Trêves internationales** : si aucun match n'est programmé dans les 7 prochains
jours, une seconde requête couvre J+7 → J+21 (les « 14 à 21 prochains jours »),
puis J+0 → J+28 en dernier recours.

**Garde-fous** : si la clé est absente, si l'API échoue (401/429/réseau) ou si
aucune affiche n'est disponible, le pipeline **conserve l'ancien fichier**
`upcoming_predictions.json` (jamais écrasé par un fichier vide). La consommation
de quota (`x-requests-remaining`) est journalisée à chaque exécution.

#### Configuration locale

```bash
cp .env.example .env
# puis renseigner ODDS_API_KEY=... dans .env
python backend/update_pipeline.py
```

La clé est lue depuis `ODDS_API_KEY` (le fichier `.env`, ignoré par git, est
chargé automatiquement en local). Plan gratuit The Odds API : 500 requêtes/mois ;
le pipeline en consomme environ 13 par exécution (13 championnats), soit ~104/mois
pour deux passages hebdomadaires.

#### Ajouter la clé dans les Secrets GitHub

1. Créer une clé sur https://the-odds-api.com/ (compte gratuit).
2. Dans le dépôt GitHub : **Settings → Secrets and variables → Actions**.
3. Onglet **Secrets**, bouton **New repository secret**.
4. Nom : `ODDS_API_KEY` — Valeur : la clé (aucun préfixe, aucun guillemet).
5. **Add secret**. Le workflow
   [`.github/workflows/auto_update.yml`](.github/workflows/auto_update.yml)
   l'injecte via `${{ secrets.ODDS_API_KEY }}` à l'exécution.

Le workflow s'exécute **mardi 08h00 UTC** (résultats du week-end) et
**jeudi 14h00 UTC** (nouvelles cotes), plus un déclenchement manuel
(`workflow_dispatch`). Il commit/push ensuite `data/upcoming_predictions.json`
(et les CSV bruts) pour que Render/Vercel servent immédiatement les nouvelles
prédictions. Les permissions d'écriture sont déjà déclarées
(`permissions: contents: write`).

### Interface — thème sombre / clair

L'interface possède un thème sombre par défaut et un thème clair, basculables à tout moment depuis la barre de navigation (bouton soleil/lune à droite). Le choix est mémorisé dans le `localStorage` et persiste d'une session à l'autre ; en l'absence de préférence, le thème suit les préférences du navigateur (`prefers-color-scheme`).

Pour activer le thème clair : cliquer sur l'icône **soleil** dans la barre de navigation, en haut à droite. Toutes les couleurs (cartes, texte, bordures, graphiques, badges) s'adaptent automatiquement grâce aux variables CSS dans [`frontend/app/globals.css`](frontend/app/globals.css).

Les fichiers concernés :

| Fichier | Rôle |
|---|---|
| `frontend/app/globals.css` | Variables CSS `--ink-*`, `--fg`, `--accent`, `--slate-*` pour thème sombre et clair (`[data-theme="light"]`) |
| `frontend/app/layout.tsx` | Initialisation du thème depuis `localStorage` ou préférence navigateur |
| `frontend/components/ThemeToggle.tsx` | Bouton bascule sombre/clair avec icônes soleil/lune |
| `frontend/components/Navbar.tsx` | Intégration du sélecteur dans la barre de navigation |

Les tables de données, graphiques Recharts et heatmaps Dixon-Coles conservent leur lisibilité dans les deux thèmes.

### Application Android (PWA)

Foot Predict est une Progressive Web App (PWA). Elle s'installe directement sur Android depuis le navigateur Chrome, sans passer par le Google Play Store.

#### Installation sur Android

1. Ouvrez l'application dans Chrome sur votre appareil Android
2. Cliquez sur le menu ⋮ (trois points) en haut à droite
3. Sélectionnez **"Ajouter à l'écran d'accueil"**
4. L'icône Foot Predict apparaît sur votre écran d'accueil

L'application s'ouvre alors en mode plein écran (sans barre d'adresse du navigateur), avec son propre icône et son nom.

#### Fichiers concernés

| Fichier | Rôle |
|---|---|
| `frontend/public/manifest.json` | Manifeste PWA (nom, icônes, raccourcis, couleurs) |
| `frontend/public/sw.js` | Service Worker (cache des ressources, mode hors-ligne) |
| `frontend/public/icons/icon.svg` | Icône de l'application (vectorielle, toutes tailles) |
| `frontend/app/layout.tsx` | Intégration du manifest, des balises méta et du service worker |

#### Fonctionnalités hors-ligne

Une fois l'application installée et ouverte au moins une fois, les ressources statiques sont mises en cache par le Service Worker. Les requêtes API tentent d'abord le réseau, puis tombent sur le cache en cas d'indisponibilité.


| Symptôme | Cause probable | Solution |
|---|---|---|
| `[WinError 10013]` au lancement d'uvicorn | Port réservé par Windows/Hyper-V, pare-feu ou antivirus | Essayer `--port 8010`, lancer sans `--reload`, ou en administrateur. Vérifier les plages réservées : `netsh interface ipv4 show excludedportrange protocol=tcp` |
| `ERR_CONNECTION_REFUSED` sur `http://localhost:3000` | Serveur Next.js non démarré ou `node_modules` absent | `cd frontend && npm install && npm run dev` |
| `frontend` renvoie « API indisponible » | Backend arrêté ou port différent | Démarrer uvicorn, vérifier `NEXT_PUBLIC_API_URL` dans `frontend/.env.local` |
| Prédictions figées pendant une trêve | `fixtures.csv` ne contient plus les championnats suivis | Renseigner `ODDS_API_KEY` puis relancer `python backend/update_pipeline.py` |
| `The Odds API a échoué (401)` | Clé absente/invalide | Vérifier `ODDS_API_KEY` (local) ou le secret GitHub |

### Variables d'environnement clés

| Service | Variable | Valeur locale | Valeur production |
|---|---|---|---|
| Backend (Render) | `ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | `https://foot-predict.vercel.app` |
| Backend (Render) | `PYTHON_VERSION` | — | `3.11.9` |
| Frontend (Vercel) | `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | `https://<service>-api.onrender.com` |
| Automatisation locale | `ODDS_API_KEY` | clé The Odds API (`.env`) | — |
| GitHub Actions | `ODDS_API_KEY` (secret) | — | clé The Odds API |
| Automatisation | `ODDS_REFERENCE_BOOKMAKERS` | `pinnacle,bet365` | `pinnacle,bet365` |
| Automatisation | `ODDS_API_REGIONS` | `eu` | `eu` |
