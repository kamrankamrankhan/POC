"""Small CNN deep-learning model for page scan quality (0-100)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np

from ..core.config import DL_MODEL_PATH, DL_ENABLED

logger = logging.getLogger(__name__)

INPUT_SIZE = 128


class QualityCNN:
    """Lazy torch CNN wrapper so the app starts even if torch is missing."""

    def __init__(self) -> None:
        self.model = None
        self.device = "cpu"
        self.metadata: Dict[str, Any] = {}
        self._torch = None
        self._nn = None
        if DL_ENABLED:
            self.load()
            if not self.is_available:
                try:
                    logger.info("No DL quality model found; training a bootstrap CNN")
                    self.train_bootstrap()
                except Exception as exc:
                    logger.warning("Could not bootstrap DL model: %s", exc)

    def _import_torch(self):
        if self._torch is not None:
            return self._torch, self._nn
        import torch
        import torch.nn as nn

        self._torch = torch
        self._nn = nn
        return torch, nn

    def _build_model(self):
        torch, nn = self._import_torch()

        class _Net(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.features = nn.Sequential(
                    nn.Conv2d(1, 16, 3, padding=1),
                    nn.ReLU(inplace=True),
                    nn.MaxPool2d(2),
                    nn.Conv2d(16, 32, 3, padding=1),
                    nn.ReLU(inplace=True),
                    nn.MaxPool2d(2),
                    nn.Conv2d(32, 64, 3, padding=1),
                    nn.ReLU(inplace=True),
                    nn.MaxPool2d(2),
                    nn.Conv2d(64, 64, 3, padding=1),
                    nn.ReLU(inplace=True),
                    nn.AdaptiveAvgPool2d((4, 4)),
                )
                self.head = nn.Sequential(
                    nn.Flatten(),
                    nn.Linear(64 * 4 * 4, 128),
                    nn.ReLU(inplace=True),
                    nn.Dropout(0.2),
                    nn.Linear(128, 1),
                )

            def forward(self, x):
                return self.head(self.features(x)).squeeze(-1)

        return _Net()

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def load(self) -> bool:
        if not DL_MODEL_PATH.exists():
            self.model = None
            self.metadata = {}
            return False
        try:
            torch, _ = self._import_torch()
            payload = torch.load(DL_MODEL_PATH, map_location="cpu", weights_only=False)
            model = self._build_model()
            model.load_state_dict(payload["state_dict"])
            model.eval()
            self.model = model
            self.metadata = payload.get("metadata", {})
            return True
        except Exception as exc:
            logger.error("Failed to load DL model: %s", exc)
            self.model = None
            self.metadata = {}
            return False

    def _preprocess(self, image_bgr: np.ndarray):
        torch, _ = self._import_torch()
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
        arr = resized.astype(np.float32) / 255.0
        tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)
        return tensor

    def predict(self, image_bgr: np.ndarray) -> Optional[float]:
        if not self.is_available:
            return None
        torch, _ = self._import_torch()
        with torch.no_grad():
            pred = float(self.model(self._preprocess(image_bgr)).item())
        return float(min(100.0, max(0.0, pred)))

    def train_bootstrap(self, samples: int = 400, epochs: int = 8) -> Dict[str, Any]:
        """Train on synthetic degraded/clean page patches labeled by heuristic sharpness."""
        torch, nn = self._import_torch()
        rng = np.random.default_rng(42)
        images = []
        labels = []

        for _ in range(samples):
            canvas = np.full((INPUT_SIZE, INPUT_SIZE), 245, dtype=np.uint8)
            # Draw fake text-like strokes
            for _line in range(int(rng.integers(6, 18))):
                y = int(rng.integers(8, INPUT_SIZE - 8))
                x0 = int(rng.integers(4, 20))
                x1 = int(rng.integers(INPUT_SIZE // 2, INPUT_SIZE - 4))
                thickness = int(rng.integers(1, 3))
                cv2.line(canvas, (x0, y), (x1, y), int(rng.integers(10, 60)), thickness)

            quality = float(rng.uniform(0.15, 1.0))
            img = canvas.astype(np.float32)
            if quality < 0.85:
                k = int(rng.choice([3, 5, 7, 9, 11]))
                img = cv2.GaussianBlur(img, (k, k), 0)
            if quality < 0.5:
                noise = rng.normal(0, 18, img.shape).astype(np.float32)
                img = np.clip(img + noise, 0, 255)
            if quality < 0.35:
                # Extra down/up sample to mimic low DPI
                small = cv2.resize(img, (INPUT_SIZE // 4, INPUT_SIZE // 4))
                img = cv2.resize(small, (INPUT_SIZE, INPUT_SIZE))

            # Label from Laplacian sharpness mapped to 0-100
            lap = cv2.Laplacian(img.astype(np.uint8), cv2.CV_64F).var()
            label = float(min(100.0, max(5.0, (lap / 80.0) * 100.0)))
            # Blend with intended quality so the CNN learns degradation cues
            label = 0.6 * label + 0.4 * (quality * 100.0)

            images.append(img.astype(np.float32) / 255.0)
            labels.append(label)

        x = torch.from_numpy(np.stack(images)[:, None, :, :])
        y = torch.from_numpy(np.asarray(labels, dtype=np.float32))

        model = self._build_model()
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        loss_fn = nn.MSELoss()
        model.train()
        batch = 32
        for epoch in range(epochs):
            perm = torch.randperm(len(x))
            total_loss = 0.0
            steps = 0
            for i in range(0, len(x), batch):
                idx = perm[i : i + batch]
                pred = model(x[idx])
                loss = loss_fn(pred, y[idx])
                opt.zero_grad()
                loss.backward()
                opt.step()
                total_loss += float(loss.item())
                steps += 1
            logger.info("DL bootstrap epoch %s loss=%.2f", epoch + 1, total_loss / max(steps, 1))

        model.eval()
        with torch.no_grad():
            preds = model(x).numpy()
        mae = float(np.mean(np.abs(preds - y.numpy())))
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "samples": samples,
            "epochs": epochs,
            "mae": mae,
            "architecture": "QualityCNN-128",
            "framework": "pytorch",
        }
        DL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "metadata": metadata}, DL_MODEL_PATH)
        self.model = model
        self.metadata = metadata
        logger.info("Saved DL quality model to %s (MAE=%.2f)", DL_MODEL_PATH, mae)
        return metadata

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": DL_ENABLED,
            "model_loaded": self.is_available,
            "model_path": str(DL_MODEL_PATH),
            "metadata": self.metadata,
        }


dl_quality_model = QualityCNN()
