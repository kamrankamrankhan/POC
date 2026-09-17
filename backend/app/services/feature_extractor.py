"""Extract numeric feature vectors from page images for ML quality prediction."""

from typing import List

import numpy as np

FEATURE_NAMES: List[str] = [
    "blur_score",
    "orientation_score",
    "cropping_score",
    "color_consistency_score",
    "dpi_score",
    "actual_dpi_norm",
    "content_density",
    "edge_density",
    "contrast",
    "text_lines_norm",
    "text_columns_norm",
    "complexity",
    "aspect_ratio",
    "brightness_mean",
]


def extract_page_features(
    image: np.ndarray,
    blur_score: float,
    orientation_score: float,
    cropping_score: float,
    color_consistency_score: float,
    dpi_score: float,
    actual_dpi: float,
) -> np.ndarray:
    """Build a fixed-length feature vector for one page."""
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape

    non_white_pixels = np.sum(gray < 240)
    content_density = non_white_pixels / max(height * width, 1)

    h_projection = np.sum(gray < 240, axis=1)
    v_projection = np.sum(gray < 240, axis=0)
    text_lines = float(np.sum(h_projection > width * 0.1))
    text_columns = float(np.sum(v_projection > height * 0.05))

    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.sum(edges > 0) / max(height * width, 1))
    contrast = float(gray.std() / 255.0)
    complexity = min(1.0, edge_density * 10 + contrast * 2)
    aspect_ratio = width / max(height, 1)
    brightness_mean = float(gray.mean() / 255.0)

    return np.array(
        [
            blur_score,
            orientation_score,
            cropping_score,
            color_consistency_score,
            dpi_score,
            min(actual_dpi / 300.0, 2.0),
            content_density,
            edge_density,
            contrast,
            text_lines / max(height, 1),
            text_columns / max(width, 1),
            complexity,
            aspect_ratio,
            brightness_mean,
        ],
        dtype=np.float32,
    )
