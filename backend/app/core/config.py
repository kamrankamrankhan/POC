import os
from pathlib import Path

# Load backend/.env if present (API keys stay out of git)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except Exception:
    pass

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# Upload settings
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
THUMBNAILS_DIR = BASE_DIR / "processed" / "thumbnails"

# Create directories if they don't exist
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
THUMBNAILS_DIR.mkdir(exist_ok=True)

# API settings
API_V1_STR = "/api/v1"
PROJECT_NAME = "PDF Scan Quality Checker"

# File processing settings
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
IMAGE_DPI = 300  # High DPI for better quality analysis
THUMBNAIL_SIZE = (200, 200)

# Quality thresholds
CONFIDENCE_THRESHOLD_HIGH = 80.0  # Auto-approve
CONFIDENCE_THRESHOLD_LOW = 20.0   # Manual review required

# DPI quality thresholds
DPI_EXCELLENT = 300.0  # Professional print quality
DPI_GOOD = 250.0       # Good quality
DPI_ACCEPTABLE = 200.0 # Acceptable quality
DPI_POOR = 150.0       # Poor quality
DPI_VERY_POOR = 100.0  # Very poor quality
DPI_MINIMUM = 75.0     # Minimum usable quality

# Blur detection thresholds
BLUR_CONTENT_DENSITY_MIN = 0.05  # Minimum content density to analyze blur
BLUR_TEXT_LINES_MIN = 3          # Minimum text lines to consider text-heavy
BLUR_TEXT_COLUMNS_MIN = 10       # Minimum text columns to consider text-heavy
BLUR_EDGE_DENSITY_MIN = 0.01     # Minimum edge density for text detection
BLUR_CONTOUR_AREA_MIN = 100      # Minimum contour area for text analysis

# Processing settings
MAX_CONCURRENT_JOBS = 5
JOB_TIMEOUT = 300  # 5 minutes

# CORS settings
BACKEND_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

# Database settings (for future use)
DATABASE_URL = "sqlite:///./pdf_quality_checker.db"

# Redis settings (for job queue)
REDIS_URL = "redis://localhost:6379"

# Logging
LOG_LEVEL = "INFO"

# Machine learning settings
MODELS_DIR = BASE_DIR / "models"
TRAINING_DATA_DIR = BASE_DIR / "data"
MODELS_DIR.mkdir(exist_ok=True)
TRAINING_DATA_DIR.mkdir(exist_ok=True)

QUALITY_MODEL_PATH = MODELS_DIR / "quality_model.joblib"
TRAINING_SAMPLES_PATH = TRAINING_DATA_DIR / "training_samples.jsonl"
DL_MODEL_PATH = MODELS_DIR / "quality_cnn.pt"

ML_ENABLED = True
ML_ENSEMBLE_WEIGHT = 0.4  # Final score = ML * weight + heuristic * (1 - weight)
ML_APPROVED_TARGET = 90.0
ML_REJECTED_TARGET = 10.0

# Deep learning (PyTorch CNN) + OCR ensemble weights applied after heuristic/ML blend
DL_ENABLED = True
OCR_ENABLED = True
DL_ENSEMBLE_WEIGHT = 0.25
OCR_ENSEMBLE_WEIGHT = 0.15
OCR_LOW_THRESHOLD = 45.0  # Flag page when OCR score is below this and text is expected

# OpenAI Vision LLM — called when DL confidence is below trigger
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
LLM_DL_TRIGGER = float(os.getenv("LLM_DL_TRIGGER", "70"))
LLM_ENSEMBLE_WEIGHT = 0.20  # Folded into final score when Vision LLM is invoked

# Microsoft Graph / SharePoint (env vars override empty defaults)
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "")
SHAREPOINT_MAX_FILES = int(os.getenv("SHAREPOINT_MAX_FILES", "200"))
