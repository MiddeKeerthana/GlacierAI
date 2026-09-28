from pathlib import Path

import geopandas as gpd
import pandas as pd

# ==========================================================
# Project Paths
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RGI_FOLDER = PROJECT_ROOT / "datasets" / "raw" / "RGI"
OUTPUT_FOLDER = PROJECT_ROOT / "datasets" / "processed"

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "global_rgi.gpkg"

# ==========================================================
# Find all shapefiles
# ==========================================================

shapefiles = sorted(RGI_FOLDER.rglob("*.shp"))

if len(shapefiles) == 0:
    raise FileNotFoundError("No shapefiles found!")

print("=" * 70)
print(f"Found {len(shapefiles)} regional glacier inventories")
print("=" * 70)

# ==========================================================
# Read all glacier inventories
# ==========================================================

all_regions = []

for shp in shapefiles:

    print(f"Reading {shp.name}")

    gdf = gpd.read_file(shp)

    gdf["SOURCE_FILE"] = shp.stem

    all_regions.append(gdf)

# ==========================================================
# Merge
# ==========================================================

print("\nMerging all glacier inventories...")

global_gdf = gpd.GeoDataFrame(
    pd.concat(all_regions, ignore_index=True),
    crs=all_regions[0].crs
)

print(f"Total glaciers : {len(global_gdf):,}")

# ==========================================================
# Save
# ==========================================================

print("\nSaving GeoPackage...")

global_gdf.to_file(
    OUTPUT_FILE,
    driver="GPKG"
)

print("\nDone!")

print("=" * 70)
print(f"Saved to:\n{OUTPUT_FILE}")
print("=" * 70)