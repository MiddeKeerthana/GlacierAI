from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import MergeAlg
from rasterio.features import rasterize

# ==========================================================
# Project Imports
# ==========================================================

from backend.app.config import SENTINEL_DATA
from backend.app.services.sentinel_reader import (
    find_safe_folder,
    get_band_path,
)

# ==========================================================
# Paths
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RGI_FILE = PROJECT_ROOT / "datasets" / "processed" / "global_rgi.gpkg"

OUTPUT_DIR = PROJECT_ROOT / "datasets" / "masks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================================
# Sentinel Tile
# ==========================================================

safe_folder = find_safe_folder(
    SENTINEL_DATA,
    "T44SKA"
)

band_path = get_band_path(
    str(safe_folder),
    "B03"
)

print("Sentinel image:")
print(band_path)

# ==========================================================
# Read Sentinel metadata
# ==========================================================

with rasterio.open(band_path) as src:
    transform = src.transform
    crs = src.crs
    width = src.width
    height = src.height
    bounds = src.bounds

print("\nImage size:")
print(f"{width} x {height}")

# ==========================================================
# Load Global RGI
# ==========================================================

print("\nLoading Global RGI...")

gdf = gpd.read_file(RGI_FILE)

print("Total glaciers:", len(gdf))

# ==========================================================
# Convert CRS
# ==========================================================

print("Converting CRS...")

gdf = gdf.to_crs(crs)

# Remove invalid geometries (just in case)

gdf = gdf[gdf.geometry.notnull()]
gdf = gdf[gdf.is_valid]

# ==========================================================
# Select glaciers inside Sentinel image
# ==========================================================

xmin = bounds.left
xmax = bounds.right
ymin = bounds.bottom
ymax = bounds.top

subset = gdf.cx[
    xmin:xmax,
    ymin:ymax
]

print("Glaciers in tile:", len(subset))

# ==========================================================
# Rasterize
# ==========================================================

print("\nRasterizing...")

mask = np.zeros((height, width), dtype=np.uint8)

if len(subset) > 0:

    rasterize(
        ((geom, 1) for geom in subset.geometry),
        out=mask,
        transform=transform,
        fill=0,
        default_value=1,
        merge_alg=MergeAlg.replace,
        dtype="uint8",
    )

else:
    print("WARNING: No glaciers intersect this Sentinel tile.")

# ==========================================================
# DEBUG
# ==========================================================

print("\n========== MASK DEBUG ==========")
print("Shape          :", mask.shape)
print("Dtype          :", mask.dtype)
print("Unique values  :", np.unique(mask))
print("Minimum        :", mask.min())
print("Maximum        :", mask.max())
print("Glacier pixels :", np.count_nonzero(mask))
print("================================")

# ==========================================================
# Save mask
# ==========================================================

output_file = OUTPUT_DIR / "gangotri_mask.tif"

print("\nBefore saving")
print("Unique:", np.unique(mask))
print("Min:", mask.min())
print("Max:", mask.max())
print("Dtype:", mask.dtype)

with rasterio.open(
    output_file,
    "w",
    driver="GTiff",
    height=height,
    width=width,
    count=1,
    dtype=rasterio.uint8,
    crs=crs,
    transform=transform,
    nodata=0,
) as dst:

    dst.write(mask.astype(np.uint8), 1)

print("\nReading saved file back...")

with rasterio.open(output_file) as src:
    saved = src.read(1)

print("Saved unique:", np.unique(saved))
print("Saved min:", saved.min())
print("Saved max:", saved.max())
print("Saved dtype:", saved.dtype)