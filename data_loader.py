"""
data_loader.py - Téléchargement et nettoyage des données Football-Data.co.uk

Ce module télécharge automatiquement les fichiers CSV des 3 dernières saisons
des 5 grands championnats européens depuis les URLs de Football-Data.co.uk,
puis nettoie et unifie les colonnes essentielles.

Il gère aussi un cache local (data/raw) : si les fichiers sont déjà présents,
aucun téléchargement n'est nécessaire (utile pour les backtests reproductibles
et pour travailler hors ligne).
"""

import os

import pandas as pd
import requests
from io import StringIO

from config import LEAGUES, SEASONS, BASE_URL, ESSENTIAL_COLUMNS, OPTIONAL_COLUMNS


def ensure_dir(path):
    """Crée un répertoire s'il n'existe pas."""
    os.makedirs(path, exist_ok=True)


def _raw_path(raw_dir, season, league_code):
    return os.path.join(raw_dir, f"{season}_{league_code}.csv")


def download_season_league(season, league_code, raw_dir="data/raw"):
    """
    Télécharge le fichier CSV d'une saison et d'un championnat donnés.

    Le CSV brut est aussi sauvegardé sur disque (data/raw) pour permettre
    l'inspection, le débogage et la réutilisation hors ligne.

    Args:
        season: Code saison au format YYZZ (ex: "2425" pour 2024-2025).
        league_code: Code championnat (ex: "E0" pour la Premier League).
        raw_dir: Répertoire de stockage des fichiers bruts.

    Returns:
        Un DataFrame pandas ou None en cas d'erreur.
    """
    url = BASE_URL.format(season=season, code=league_code)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Sauvegarde du fichier brut sur disque
        ensure_dir(raw_dir)
        with open(_raw_path(raw_dir, season, league_code), "w", encoding="utf-8") as f:
            f.write(response.text)

        return pd.read_csv(StringIO(response.text.lstrip("\ufeff")))
    except Exception as exc:
        print(f"[ERREUR] Téléchargement {season}/{league_code}: {exc}")
        return None


def load_cached_data(raw_dir="data/raw"):
    """
    Charge les CSV bruts déjà téléchargés depuis data/raw.

    Returns:
        DataFrame concaténé ou None si aucun fichier de cache n'est disponible.
    """
    frames = []
    for league_name, info in LEAGUES.items():
        code = info["code"]
        for season in SEASONS:
            path = _raw_path(raw_dir, season, code)
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except Exception as exc:
                print(f"[ERREUR] Lecture cache {path}: {exc}")
                continue
            if df.empty:
                continue
            df = df.copy()
            df["Saison"] = season
            df["Championnat"] = league_name
            df["CodeChampionnat"] = code
            frames.append(df)
            print(f"[CACHE] {league_name} saison {season}: {len(df)} matchs")

    return pd.concat(frames, ignore_index=True) if frames else None


def _parse_dates(date_series):
    """
    Convertit une série de dates en datetime avec plusieurs tentatives de format.

    Football-Data.co.uk utilise des formats variables selon les fichiers :
    DD/MM/YY, DD/MM/YYYY, etc. On essaie plusieurs formats avant le repli
    automatique de pandas.

    Returns:
        Série de datetime (NaT pour les valeurs non interprétables).
    """
    formats = ["%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%y", "%m/%d/%Y"]
    for fmt in formats:
        parsed = pd.to_datetime(date_series, format=fmt, errors="coerce")
        # Si au moins une date a été interprétée et que ce n'est pas tout NaT, on retient
        if not parsed.isna().all():
            # On accepte ce format s'il interprète la majorité des valeurs
            non_na_ratio = parsed.notna().mean()
            if non_na_ratio > 0.5:
                return parsed
    # Repli final : détection automatique de pandas
    return pd.to_datetime(date_series, errors="coerce")


def load_all_data(raw_dir="data/raw"):
    """
    Télécharge et concatène toutes les saisons de tous les championnats configurés.

    Returns:
        DataFrame brut contenant tous les matchs téléchargés.
    """
    ensure_dir(raw_dir)
    all_frames = []

    for league_name, info in LEAGUES.items():
        code = info["code"]
        for season in SEASONS:
            df = download_season_league(season, code, raw_dir)
            if df is not None and not df.empty:
                df = df.copy()
                df["Saison"] = season
                df["Championnat"] = league_name
                df["CodeChampionnat"] = code
                all_frames.append(df)
                print(f"[OK] {league_name} saison {season}: {len(df)} matchs")
            else:
                print(f"[VIDE] {league_name} saison {season}")

    if not all_frames:
        raise RuntimeError("Aucune donnée n'a pu être téléchargée depuis Football-Data.co.uk.")

    return pd.concat(all_frames, ignore_index=True)


def clean_data(df):
    """
    Nettoie le DataFrame et conserve uniquement les colonnes utiles.

    Colonnes essentielles : Date, HomeTeam, AwayTeam, FTHG, FTAG, B365H, B365D, B365A
    Colonnes optionnelles : AvgH, AvgD, AvgA (cotes moyennes du marché)
    Métadonnées : Saison, Championnat, CodeChampionnat.

    Returns:
        DataFrame nettoyé, trié chronologiquement, sans valeurs manquantes critiques.
    """
    print(f"[DEBUG] Nettoyage : {len(df)} lignes brutes au départ")

    # Vérifier la présence des colonnes essentielles
    missing = [c for c in ESSENTIAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes essentielles manquantes dans le CSV: {missing}")

    optional_present = [c for c in OPTIONAL_COLUMNS if c in df.columns]
    keep_cols = (
        ESSENTIAL_COLUMNS
        + optional_present
        + ["Saison", "Championnat", "CodeChampionnat"]
    )
    df = df[keep_cols].copy()

    # Les colonnes optionnelles absentes sont créées vides pour garder un schéma stable
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = float("nan")

    # Conversion des dates avec plusieurs formats possibles
    df["Date"] = _parse_dates(df["Date"])
    date_nat_count = df["Date"].isna().sum()
    print(f"[DEBUG] Après conversion de date : {date_nat_count} NaT sur {len(df)} lignes")

    # Conversion des colonnes numériques
    numeric_cols = ["FTHG", "FTAG", "B365H", "B365D", "B365A"] + OPTIONAL_COLUMNS
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Nombre de lignes avec des données de score manquantes (matchs non joués)
    score_na = df[["FTHG", "FTAG"]].isna().any(axis=1).sum()
    print(f"[DEBUG] Lignes avec score manquant (non joués) : {score_na}")

    # Suppression des lignes avec des données critiques manquantes
    before_drop = len(df)
    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
    after_drop = len(df)
    print(f"[DEBUG] Après dropna : {after_drop} lignes (supprimé {before_drop - after_drop})")

    # Nettoyage des noms d'équipes
    df["HomeTeam"] = df["HomeTeam"].astype(str).str.strip()
    df["AwayTeam"] = df["AwayTeam"].astype(str).str.strip()

    # Suppression des noms d'équipe vides
    df = df[(df["HomeTeam"] != "") & (df["AwayTeam"] != "")]

    # Tri chronologique indispensable pour le calcul Elo dynamique (pas de fuite de données)
    df = df.sort_values("Date").reset_index(drop=True)
    print(f"[DEBUG] Nettoyage terminé : {len(df)} matchs propres")
    return df


def fetch_and_clean(raw_dir="data/raw", use_cache=True):
    """
    Pipeline complet : récupération des données (cache ou téléchargement) + nettoyage.

    Args:
        raw_dir: Répertoire des CSV bruts.
        use_cache: Si True (défaut), réutilise les fichiers déjà présents dans
                   raw_dir avant de tenter un téléchargement.

    Returns:
        DataFrame propre et trié, prêt à être utilisé par le moteur de prédiction.
    """
    raw_df = load_cached_data(raw_dir) if use_cache else None
    if raw_df is None or raw_df.empty:
        if use_cache:
            print("[CACHE] Aucun fichier local exploitable, téléchargement ...")
        raw_df = load_all_data(raw_dir)

    clean_df = clean_data(raw_df)
    print(f"\n[TOTAL] {len(clean_df)} matchs propres chargés.")
    return clean_df
