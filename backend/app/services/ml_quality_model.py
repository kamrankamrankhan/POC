"""Scikit-learn quality model: train, persist, and predict page confidence scores."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

from ..core.config import (
    ML_APPROVED_TARGET,
    ML_REJECTED_TARGET,
    QUALITY_MODEL_PATH,
    TRAINING_SAMPLES_PATH,
)
from .feature_extractor import FEATURE_NAMES

logger = logging.getLogger(__name__)


class QualityMLModel:
    """Random Forest regressor predicting page quality confidence (0-100)."""

    def __init__(self) -> None:
        self.model: Optional[RandomForestRegressor] = None
        self.metadata: Dict[str, Any] = {}
        self.load()
        if not self.is_available:
            try:
                logger.info("No quality ML model found; training a bootstrap model")
                self.train()
            except Exception as exc:
                logger.warning("Could not bootstrap ML model: %s", exc)

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def load(self) -> bool:
        if not QUALITY_MODEL_PATH.exists():
            self.model = None
            self.metadata = {}
            return False

        try:
            payload = joblib.load(QUALITY_MODEL_PATH)
            self.model = payload["model"]
            self.metadata = payload.get("metadata", {})
            return True
        except Exception as exc:
            logger.error("Failed to load ML model: %s", exc)
            self.model = None
            self.metadata = {}
            return False

    def predict(self, features: np.ndarray) -> Optional[float]:
        if not self.is_available:
            return None

        vector = np.asarray(features, dtype=np.float32).reshape(1, -1)
        prediction = float(self.model.predict(vector)[0])
        return min(100.0, max(0.0, prediction))

    def append_training_sample(self, features: np.ndarray, target: float) -> None:
        TRAINING_SAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "features": np.asarray(features, dtype=np.float32).tolist(),
            "target": float(target),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with TRAINING_SAMPLES_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def load_training_samples(self) -> tuple[np.ndarray, np.ndarray]:
        if not TRAINING_SAMPLES_PATH.exists():
            return np.empty((0, len(FEATURE_NAMES))), np.empty((0,))

        features: List[List[float]] = []
        targets: List[float] = []
        with TRAINING_SAMPLES_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                features.append(record["features"])
                targets.append(record["target"])

        if not features:
            return np.empty((0, len(FEATURE_NAMES))), np.empty((0,))

        return np.asarray(features, dtype=np.float32), np.asarray(targets, dtype=np.float32)

    def train(
        self,
        extra_features: Optional[np.ndarray] = None,
        extra_targets: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        stored_features, stored_targets = self.load_training_samples()
        feature_sets = [stored_features]
        target_sets = [stored_targets]

        if extra_features is not None and extra_targets is not None and len(extra_features):
            feature_sets.append(extra_features)
            target_sets.append(extra_targets)

        bootstrap_features, bootstrap_targets = _generate_bootstrap_dataset()
        feature_sets.append(bootstrap_features)
        target_sets.append(bootstrap_targets)

        x_train = np.vstack(feature_sets)
        y_train = np.concatenate(target_sets)

        if len(x_train) < 20:
            raise ValueError("Not enough training samples to train the model")

        x_fit, x_test, y_fit, y_test = train_test_split(
            x_train, y_train, test_size=0.2, random_state=42
        )

        model = RandomForestRegressor(
            n_estimators=120,
            max_depth=12,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(x_fit, y_fit)

        train_score = float(model.score(x_fit, y_fit))
        test_score = float(model.score(x_test, y_test)) if len(x_test) else train_score

        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "sample_count": int(len(x_train)),
            "review_sample_count": int(len(stored_features)),
            "feature_names": FEATURE_NAMES,
            "train_r2": train_score,
            "test_r2": test_score,
            "approved_target": ML_APPROVED_TARGET,
            "rejected_target": ML_REJECTED_TARGET,
        }

        QUALITY_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": model, "metadata": metadata}, QUALITY_MODEL_PATH)

        self.model = model
        self.metadata = metadata
        logger.info(
            "Trained quality ML model on %s samples (test R2=%.3f)",
            len(x_train),
            test_score,
        )
        return metadata

    def get_status(self) -> Dict[str, Any]:
        stored_features, _ = self.load_training_samples()
        return {
            "enabled": True,
            "model_loaded": self.is_available,
            "model_path": str(QUALITY_MODEL_PATH),
            "training_samples_path": str(TRAINING_SAMPLES_PATH),
            "review_sample_count": int(len(stored_features)),
            "metadata": self.metadata,
        }


def _generate_bootstrap_dataset(size: int = 800) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic bootstrap data aligned with the heuristic scoring engine."""
    rng = np.random.default_rng(42)
    features = rng.uniform(0.0, 1.0, size=(size, len(FEATURE_NAMES))).astype(np.float32)
    features[:, 5] = rng.uniform(0.2, 1.2, size=size)
    features[:, 6:14] = rng.uniform(0.0, 1.0, size=(size, 8))

    weights = np.array([0.3, 0.15, 0.15, 0.15, 0.25], dtype=np.float32)
    heuristic = (
        features[:, 0] * weights[0]
        + features[:, 1] * weights[1]
        + features[:, 2] * weights[2]
        + features[:, 3] * weights[3]
        + features[:, 4] * weights[4]
    ) * 100.0
    noise = rng.normal(0.0, 4.0, size=size)
    targets = np.clip(heuristic + noise, 0.0, 100.0).astype(np.float32)
    return features, targets


quality_ml_model = QualityMLModel()
