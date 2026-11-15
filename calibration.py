"""
calibration.py - Calibration des probabilités 1X2 (isotonique par issue).

Le moteur produit des probabilités structurées (Poisson + Dixon-Coles + mélange
vers les fréquences de base) mais systématiquement trop tranchées sur les
extrêmes. La calibration isotonique apprend une fonction monotone
« probabilité brute -> probabilité observée » sur un historique de prédictions
hors échantillon (walk-forward), sans jamais utiliser le futur.

Implémentation sans dépendance externe :
  - régression isotonique par l'algorithme PAVA (Pool Adjacent Violators) ;
  - une courbe par issue (domicile, nul, extérieur), puis renormalisation ;
  - sérialisation JSON des points de rupture.

Usage :
    from calibration import Calibrated1X2
    calibrator = Calibrated1X2.fit(probabilities, outcomes)
    probs = calibrator.transform_single((0.52, 0.24, 0.24))
"""

from __future__ import annotations

import json
import os

import numpy as np


def _pava(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Pool Adjacent Violators : ajustement monotone croissant pondéré."""
    blocks: list[list[float]] = []  # [poids, moyenne, cardinal]
    for value, weight in zip(values, weights):
        blocks.append([float(weight), float(value), 1])
        while len(blocks) > 1 and blocks[-2][1] >= blocks[-1][1]:
            weight_b, mean_b, count_b = blocks.pop()
            weight_a, mean_a, count_a = blocks.pop()
            total_weight = weight_a + weight_b
            blocks.append([
                total_weight,
                (mean_a * weight_a + mean_b * weight_b) / total_weight,
                count_a + count_b,
            ])
    fitted: list[float] = []
    for _, mean, count in blocks:
        fitted.extend([mean] * count)
    return np.asarray(fitted, dtype=float)


class IsotonicCalibrator:
    """Courbe isotonique d'une issue (probabilité prédite -> fréquence observée)."""

    def __init__(self, xs, ys):
        self.x = np.asarray(xs, dtype=float)
        self.y = np.asarray(ys, dtype=float)

    @classmethod
    def fit(cls, scores, targets) -> "IsotonicCalibrator":
        scores = np.asarray(scores, dtype=float)
        targets = np.asarray(targets, dtype=float)
        if scores.size == 0:
            return cls([0.0, 1.0], [0.0, 1.0])

        order = np.argsort(scores, kind="mergesort")
        sorted_scores = scores[order]
        sorted_targets = targets[order]
        fitted = _pava(sorted_targets, np.ones_like(sorted_targets))

        xs: list[float] = []
        ys: list[float] = []
        for value in np.unique(sorted_scores):
            mask = sorted_scores == value
            xs.append(float(value))
            ys.append(float(fitted[mask].mean()))

        # Garde-fou : au moins deux points pour l'interpolation
        if len(xs) == 1:
            xs = [0.0, 1.0]
            ys = [ys[0], ys[0]]
        return cls(xs, ys)

    def transform(self, scores) -> np.ndarray:
        return np.interp(
            np.asarray(scores, dtype=float),
            self.x,
            self.y,
            left=float(self.y[0]),
            right=float(self.y[-1]),
        )

    def to_dict(self) -> dict:
        return {"x": self.x.tolist(), "y": self.y.tolist()}

    @classmethod
    def from_dict(cls, data: dict) -> "IsotonicCalibrator":
        return cls(data["x"], data["y"])


class Calibrated1X2:
    """Calibrateur multiclasse : une courbe isotonique par issue + renormalisation."""

    def __init__(self, models: list[IsotonicCalibrator]):
        self.models = models

    @classmethod
    def fit(cls, probabilities, outcomes) -> "Calibrated1X2":
        probs = np.asarray(probabilities, dtype=float)
        outcomes = np.asarray(outcomes)
        models = [
            IsotonicCalibrator.fit(probs[:, index], (outcomes == index).astype(float))
            for index in range(3)
        ]
        return cls(models)

    def transform(self, probabilities) -> np.ndarray:
        probs = np.asarray(probabilities, dtype=float)
        if probs.ndim == 1:
            probs = probs.reshape(1, -1)
        calibrated = np.column_stack([
            model.transform(probs[:, index]) for index, model in enumerate(self.models)
        ])
        calibrated = np.clip(calibrated, 1e-6, 1.0)
        totals = calibrated.sum(axis=1, keepdims=True)
        return calibrated / totals

    def transform_single(self, probabilities) -> tuple[float, float, float]:
        row = self.transform(probabilities)[0]
        return float(row[0]), float(row[1]), float(row[2])

    def to_dict(self) -> dict:
        return {"models": [model.to_dict() for model in self.models]}

    @classmethod
    def from_dict(cls, data: dict) -> "Calibrated1X2":
        return cls([IsotonicCalibrator.from_dict(model) for model in data["models"]])


def save(path: str, calibrator: Calibrated1X2) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(calibrator.to_dict(), handle)
    os.replace(tmp, path)


def load(path: str) -> Calibrated1X2 | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return Calibrated1X2.from_dict(json.load(handle))
    except Exception:
        return None
