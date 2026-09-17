#!/usr/bin/env python3
"""Bootstrap and train the PDF quality ML model."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.ml_quality_model import quality_ml_model  # noqa: E402


def main() -> None:
    metadata = quality_ml_model.train()
    quality_ml_model.load()
    print("Quality ML model trained successfully.")
    print(f"Samples: {metadata['sample_count']}")
    print(f"Review samples: {metadata['review_sample_count']}")
    print(f"Test R2: {metadata['test_r2']:.3f}")
    print(f"Model saved to: {quality_ml_model.get_status()['model_path']}")


if __name__ == "__main__":
    main()
