from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from backend.app.config import SENTINEL_DATA
from backend.app.services.sentinel_reader import (
    find_safe_folder,
    get_band_path,
)

# ==========================================================
# Configuration
# ==========================================================

PATCH_SIZE = 256
STRIDE = 128
MIN_GLACIER_RATIO = 0.02

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MASK_PATH = PROJECT_ROOT / "datasets" / "masks" / "gangotri_mask.tif"

OUTPUT_IMAGES = PROJECT_ROOT / "datasets" / "training" / "images"
OUTPUT_MASKS = PROJECT_ROOT / "datasets" / "training" / "masks"

OUTPUT_IMAGES.mkdir(parents=True, exist_ok=True)
OUTPUT_MASKS.mkdir(parents=True, exist_ok=True)

# ==========================================================
# Locate Sentinel tile
# ==========================================================

safe_folder = find_safe_folder(
    SENTINEL_DATA,
    "T44SKA"
)

red_path = get_band_path(str(safe_folder), "B04")
green_path = get_band_path(str(safe_folder), "B03")
blue_path = get_band_path(str(safe_folder), "B02")

# ==========================================================
# Read RGB bands
# ==========================================================

with rasterio.open(red_path) as src:
    red = src.read(1)

with rasterio.open(green_path) as src:
    green = src.read(1)

with rasterio.open(blue_path) as src:
    blue = src.read(1)

# ==========================================================
# Normalize
# ==========================================================

def normalize(band):
    band = band.astype(np.float32)

    band = (band - np.percentile(band, 2)) / (
        np.percentile(band, 98) - np.percentile(band, 2)
    )

    band = np.clip(band, 0, 1)

    return (band * 255).astype(np.uint8)

red = normalize(red)
green = normalize(green)
blue = normalize(blue)

rgb = np.dstack((red, green, blue))

# ==========================================================
# Read glacier mask
# ==========================================================

with rasterio.open(MASK_PATH) as src:
    mask = src.read(1)

# ==========================================================
# Generate patches
# ==========================================================

patch_id = 0
saved = 0
discarded = 0

height, width = mask.shape

for y in range(0, height - PATCH_SIZE + 1, STRIDE):

    for x in range(0, width - PATCH_SIZE + 1, STRIDE):

        rgb_patch = rgb[y:y+PATCH_SIZE, x:x+PATCH_SIZE]

        mask_patch = mask[y:y+PATCH_SIZE, x:x+PATCH_SIZE]

        glacier_ratio = np.count_nonzero(mask_patch) / mask_patch.size

        if glacier_ratio < MIN_GLACIER_RATIO:
            discarded += 1
            continue

        Image.fromarray(rgb_patch).save(
            OUTPUT_IMAGES / f"patch_{patch_id:05d}.png"
        )

        Image.fromarray(mask_patch * 255).save(
            OUTPUT_MASKS / f"patch_{patch_id:05d}.png"
        )

        saved += 1
        patch_id += 1

print("\n==========================")
print("Patch generation complete")
print("==========================")
print("Saved patches     :", saved)
print("Discarded patches :", discarded)