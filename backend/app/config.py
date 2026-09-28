from pathlib import Path

# GlacierAI project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Datasets
DATASETS = PROJECT_ROOT / "datasets"

SENTINEL_DATA = DATASETS / "raw" / "Sentinel2"

# Backend folders
UPLOADS = PROJECT_ROOT / "backend" / "uploads"

TRAINED_MODELS = PROJECT_ROOT / "backend" / "trained_models"