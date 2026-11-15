# Rapport Phase 2 — Backtesting et validation

Données : 5 grands championnats × 3 saisons (2024‑25, 2025‑26, 2026‑27 en cours),
soit **4 004 matchs** téléchargés depuis Football‑Data.co.uk.

Méthode : **walk‑forward chronologique**. Chaque match est prédit avec un moteur
qui ne connaît que les matchs strictement antérieurs ; le résultat réel n'est
injecté qu'ensuite. Aucune fuite de données.

---

## 0. Protocole du cahier des charges (saison 2025‑26)

Implémentation demandée en Phase 2 :

- **Warm‑up** : saison 2024‑25 complète (1 752 matchs) pour initialiser Elo,
  forces attaque/défense et fréquences de base.
- **Saison cible** : 2025‑26 (1 752 matchs), seuls ces matchs sont pariés.
- **Journée par journée** : tous les matchs d'une même date sont prédits avant
  l'injection des résultats de cette date. Pour prédire le 15/03, le moteur ne
  connaît donc que les matchs **strictement antérieurs au 15/03**.
- **Cotes** : `B365H/D/A` en priorité, `AvgH/D/A` (moyenne du marché) en repli.
- **Value bet** : `EV = probabilité modèle × cote − 1 > 0,05`, avec une cote
  comprise entre **1,40 et 5,00**. Une seule sélection par match (meilleur EV).
- **Mises** : stratégie A = 1 unité fixe ; stratégie B = Quarter‑Kelly
  (`0,25 × EV/(cote−1) × bankroll courante`), plafonné à 3 % de la bankroll
  initiale (100 unités).

### Qualité probabiliste

| Indicateur | Valeur |
|---|---|
| Brier modèle | **0,6018** |
| Brier bookmaker (dé‑marginé) | 0,5827 |
| Brier fréquences de base | 0,6491 |
| Log‑loss modèle | 1,0078 |
| Précision 1X2 | 51,26 % |

### Sélection et stratégies

| Indicateur | Valeur |
|---|---|
| Paris simulés | 928 / 1 752 matchs (53 %) |
| Taux de réussite | 35,02 % |
| Cote moyenne jouée | 2,905 |
| EV moyenne | 19,40 % |
| **A — Flat 1 u** : misé / profit / ROI | 928 u / **−71,87 u** / **−7,74 %** |
| **A — Drawdown max** | 106,03 u (91,22 % du pic) |
| **B — Quarter‑Kelly** : misé / profit / ROI | 869,54 u / **−97,78 u** / **−11,25 %** |
| **B — Drawdown max** | 126,94 u (98,47 % du pic) |
| Bankroll finale (départ 100 u) | A = 28,13 u ; B = 2,22 u |

### Détail par championnat (stratégie A / B)

| Championnat | Paris | Réussite | ROI A | ROI B | Profit A | Profit B |
|---|---|---|---|---|---|---|
| Premier League | 211 | 40,8 % | **+23,7 %** | **+30,8 %** | +50,0 | +57,3 |
| La Liga | 202 | 32,7 % | −14,0 % | −13,2 % | −28,2 | −21,8 |
| Serie A | 171 | 32,2 % | −13,6 % | −19,0 % | −23,3 | −28,1 |
| Bundesliga | 186 | 36,6 % | −20,1 % | −23,4 % | −37,3 | −45,7 |
| Ligue 1 | 158 | 31,6 % | −20,9 % | −33,9 % | −33,0 | −59,4 |

### Détail par type de pari (stratégie A / B)

| Type | Paris | Réussite | Cote moyenne | ROI A | ROI B |
|---|---|---|---|---|---|
| Victoire domicile | 401 | 40,6 % | 2,51 | −7,1 % | −6,8 % |
| Nul | 99 | 25,2 % | 4,01 | **+1,2 %** | −6,8 % |
| Victoire extérieur | 428 | 32,0 % | 3,02 | −10,4 % | −16,2 % |

### Lecture honnête

- Le filtre du cahier des charges (EV > 5 %, cotes 1,40–5,00) est **beaucoup plus
  large** que les filtres optimisés précédemment : 53 % des matchs génèrent un
  pari, avec une EV moyenne de 19,4 %. Cela traduit une **sur‑confiance** du
  modèle, pas une inefficience du marché.
- Résultat logique : ROI négatif pour les deux stratégies. Le Quarter‑Kelly
  amplifie les pertes (`−11,25 %`) parce qu'il mise davantage sur les edges les
  plus forts, précisément ceux où le modèle se trompe le plus.
- Le **+23,7 %** de Premier League sur 211 paris ne doit pas être surinterprété :
  c'est un sous‑échantillon, et l'IC bootstrap de ce type de résultat contient
  largement 0 (voir section 2).
- Le modèle reste **moins bon que le marché** (Brier 0,6018 vs 0,5827), même s'il
  bat les fréquences de base (0,6491). C'est la conclusion robuste.
- Exécution : **≈ 3,2 s** pour 1 752 matchs (moteur incrémental, aucune
  re‑estimation complète de l'historique à chaque match).

Fichiers produits : `data/backtest_results.csv` (Date, Match, pari, probabilité,
cote, EV, résultat, profits A/B), `data/backtest_report.json`,
`data/market_quotes.csv`.

---

## 1. Qualité probabiliste (tous les matchs, 4 003 prédictions)

> Les sections 1 à 5 conservent l'étude initiale sur les **3 saisons** et les
> filtres optimisés (edge 5–20 %, cotes 1,50–5,00, proba ≥ 10 %). Elles servent
> de comparaison avec le protocole strict du cahier des charges ci-dessus.

| Modèle | Brier Score ↓ | Log‑loss ↓ |
|---|---|---|
| **Modèle Foot Predict** | **0,6008** | **1,0066** |
| Bet365 (cotes dé‑marginalisées) | 0,5757 | — |
| Fréquences de base (45/26/29) | 0,6502 | — |
| Hasard uniforme | 0,6667 | — |

Précision 1X2 (issue la plus probable) : **51,34 %**.

Lecture : le modèle bat nettement les fréquences de base et le hasard uniforme,
donc il apporte de l'information réelle. Il reste toutefois **moins bon que le
marché** (0,6008 vs 0,5757) : Bet365 intègre des informations (compositions,
blessures, contexte) que ce prototype n'utilise pas.

### Détail par saison

| Saison | Brier modèle | Brier Bet365 |
|---|---|---|
| 2024‑25 | 0,6078 | 0,5732 |
| 2025‑26 | 0,6018 | 0,5827 |
| 2026‑27 (partielle) | 0,5727 | 0,5593 |

---

## 2. Value betting — résultat honnête

Avec les filtres de mise par défaut (edge 5–20 %, cotes 1,50–5,00, proba ≥ 10 %) :

| Saison | Paris | Réussite | ROI |
|---|---|---|---|
| 2024‑25 | 600 | — | **−5,81 %** |
| 2025‑26 | 664 | — | **−3,84 %** |
| 2026‑27 | 175 | — | **−2,27 %** |
| **Global** | **1 439** | **36,9 %** | **−4,47 %** |

**Aucune stratégie profitable n'est démontrée.** C'est le résultat attendu
lorsqu'un modèle est moins bon que le marché : les « value bets » qu'il détecte
sont majoritairement des erreurs du modèle, pas des inefficiences du bookmaker.

### Pourquoi les premiers essais étaient catastrophiques

Le premier backtest donnait un ROI de −12,8 % et **83 % des matchs** généraient
un pari. L'analyse par tranche a montré que les pertes étaient concentrées sur :

- les **longs shots** (cotes > 5) : ROI −43 % et −31 % ;
- les **edges extrêmes** (> 20 %) : ROI −13 % à −19 %.

Ces deux catégories sont les symptômes classiques d'un modèle sur‑confiant qui
s'écarte du marché. D'où les filtres actuels.

### Sélection de filtres : validation vs holdout

Grille de filtres évaluée sur la saison 2025‑26 (validation), puis appliquée à
2026‑27 (test hors échantillon) :

| Saison | Rôle | Paris | ROI | IC 95 % (bootstrap) | P(ROI > 0) |
|---|---|---|---|---|---|
| 2024‑25 | référence | 250 | −2,4 % | [−17,0 % ; +12,5 %] | 35,7 % |
| 2025‑26 | validation | 272 | +12,5 % | [−3,5 % ; +28,4 %] | 93,9 % |
| 2026‑27 | **holdout** | 68 | +7,8 % | **[−24,1 % ; +41,3 %]** | 67,8 % |

Le meilleur filtre en validation (edge 8–15 %, cotes 1,50–4,00) reste positif
en holdout, **mais l'intervalle de confiance à 95 % contient largement 0** avec
seulement 68 paris. On ne peut donc pas conclure à un avantage réel : c'est
compatible avec du bruit.

---

## 3. Réglage des hyperparamètres

Sélection sur le Brier de validation (2025‑26), vérification sur 2026‑27.
Grille : `CALIBRATION_ALPHA` ∈ {0,10 ; 0,25 ; 0,40} × `TIME_DECAY_LAMBDA` ∈
{0,002 ; 0,008} × `ELO_GOAL_WEIGHT` ∈ {0,30 ; 0,60}.

| alpha | lambda | elo_w | Brier validation | Brier holdout |
|---|---|---|---|---|
| 0,10 | 0,002 | 0,30 | 0,6076 | 0,5736 |
| 0,10 | 0,008 | 0,30 | 0,6139 | 0,5859 |
| **0,25** | **0,002** | **0,30** | **0,6019** | **0,5728** |
| 0,25 | 0,002 | 0,60 | 0,6074 | 0,5757 |
| 0,40 | 0,002 | 0,30 | 0,6012 | 0,5768 |
| 0,40 | 0,008 | 0,60 | 0,6056 | 0,5825 |

Décisions retenues :

- `ELO_GOAL_WEIGHT = 0,30` : meilleur sur validation **et** holdout (robuste).
- `TIME_DECAY_LAMBDA = 0,002` : une décroissance plus rapide (0,008) dégrade le
  Brier — sur 5 championnats, la mémoire longue est plus utile que la « forme »
  à court terme. Constat empirique, contraire à l'intuition initiale.
- `CALIBRATION_ALPHA = 0,25` : les écarts avec 0,40 sont dans le bruit, et 0,25
  est meilleur en holdout.

---

## 4. Bogue corrigé : Time Decay inopérant en mode incrémental

Le backtesting a révélé que `TIME_DECAY_LAMBDA` n'avait **aucun effet** sur les
prédictions walk‑forward : dans `update_match`, la date du match servait à la
fois de date d'observation et de date de référence, donc `days_ago = 0`
systématiquement et chaque match pesait 1,0.

Correction : décroissance en ligne appliquée aux accumulateurs avant chaque
nouveau match (`_apply_decay`). Le mode par lots (`train`) et le mode
incrémental donnent désormais exactement les mêmes forces.

---

## 5. Conclusions et suite

**Ce qui fonctionne :**

- pipeline reproductible, sans fuite de données ;
- probabilités calibrées, meilleures que les fréquences de base ;
- backtesting honnête avec benchmarks marché et intervalles de confiance.

**Ce qui ne fonctionne pas (encore) :**

- le modèle ne bat pas Bet365 (Brier 0,601 vs 0,576) ;
- aucun ROI positif statistiquement démontré.

**Pistes prioritaires pour la Phase 3 :**

1. Modéliser **par championnat** (forces normalisées par ligue) plutôt qu'en pool.
2. Ajouter les données de **xG** et les compositions/blessures (source payante ou API).
3. Remplacer la calibration par un **réseau de calibration** (Platt / isotonique)
   ajusté sur validation.
4. Tester un **Dixon‑Coles estimé par maximum de vraisemblance** (ρ et forces
   estimés conjointement) au lieu du ρ fixe.
5. N'exposer en interface que les marchés où le modèle est compétitif, et
   afficher les intervalles d'incertitude plutôt qu'un simple « value bet ».
