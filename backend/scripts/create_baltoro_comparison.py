"""
Create a full-glacier visual comparison for an already-processed large glacier.

Outputs:
1. <glacier>_full_rgb.png
2. <glacier>_prediction_overlay.png
3. <glacier>_rgi_vs_prediction.png
4. <glacier>_comparison.png

Expected existing files:
datasets/live/<glacier>_glacier_tile_001.tif
datasets/live/<glacier>_glacier_tile_002.tif
...
datasets/live/predictions/<glacier>_glacier_tile_001_glacier_mask.tif
...
"""

from pathlib import Path
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.features import rasterize
from rasterio.plot import plotting_extent
import geopandas as gpd
from PIL import Image, ImageDraw

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.rgi_service import find_glacier_by_name


GLACIER_NAME = "Baltoro Glacier"

BASE_DIR = Path(__file__).resolve().parents[2]
LIVE_DIR = BASE_DIR / "datasets" / "live"
PRED_DIR = LIVE_DIR / "predictions"
OUT_DIR = LIVE_DIR / "large_glacier"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def percentile_normalize(rgb):
    """Normalize UINT16 Sentinel reflectance into an 8-bit display image."""
    rgb = rgb.astype(np.float32)

    out = np.zeros_like(rgb, dtype=np.uint8)

    for b in range(3):
        band = rgb[b]
        valid = band[np.isfinite(band) & (band > 0)]

        if valid.size == 0:
            continue

        lo, hi = np.percentile(valid, [2, 98])

        if hi <= lo:
            lo = float(valid.min())
            hi = float(valid.max())

        if hi > lo:
            scaled = (band - lo) / (hi - lo)
        else:
            scaled = np.zeros_like(band)

        out[b] = np.clip(scaled * 255, 0, 255).astype(np.uint8)

    return np.transpose(out, (1, 2, 0))


def load_tile_paths():
    tiles = sorted(LIVE_DIR.glob("baltoro_glacier_tile_*.tif"))

    # Ignore unrelated files if any.
    tiles = [
        p for p in tiles
        if p.name.endswith(".tif")
        and "_tile_" in p.name
    ]

    if not tiles:
        raise FileNotFoundError(
            f"No tile GeoTIFFs found in {LIVE_DIR}"
        )

    return tiles


def load_mask_paths(tile_paths):
    masks = []

    for tile in tile_paths:
        mask_name = tile.stem + "_glacier_mask.tif"
        mask_path = PRED_DIR / mask_name

        if not mask_path.exists():
            raise FileNotFoundError(
                f"Missing prediction mask:\n{mask_path}"
            )

        masks.append(mask_path)

    return masks


def get_rgi_geometry():
    glacier = find_glacier_by_name(GLACIER_NAME)

    if glacier is None:
        raise RuntimeError(f"RGI glacier not found: {GLACIER_NAME}")

    geometry = glacier.get("geometry")

    if geometry is None:
        raise RuntimeError(
            "RGI geometry was not returned for the glacier."
        )

    return geometry, glacier


def make_overlay(rgb, prediction_mask, rgi_mask):
    """
    Create an RGB comparison:
      - predicted glacier = red translucent fill
      - RGI boundary = yellow line
      - overlap = visible where prediction follows RGI
    """
    base = Image.fromarray(rgb).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

    pred = prediction_mask.astype(bool)
    rgi = rgi_mask.astype(bool)

    # Red prediction fill.
    pred_rgba = np.zeros((pred.shape[0], pred.shape[1], 4), dtype=np.uint8)
    pred_rgba[pred] = [255, 0, 0, 95]

    pred_img = Image.fromarray(pred_rgba, mode="RGBA")
    base = Image.alpha_composite(base, pred_img)

    # RGI boundary from mask edge.
    edge = rgi & ~(
        np.roll(rgi, 1, axis=0)
        & np.roll(rgi, -1, axis=0)
        & np.roll(rgi, 1, axis=1)
        & np.roll(rgi, -1, axis=1)
    )

    boundary = np.zeros((rgi.shape[0], rgi.shape[1], 4), dtype=np.uint8)
    boundary[edge] = [255, 230, 0, 255]

    boundary_img = Image.fromarray(boundary, mode="RGBA")
    base = Image.alpha_composite(base, boundary_img)

    return base.convert("RGB")


def main():
    print("\n==========================================")
    print(" GLACIERAI - VISUAL COMPARISON")
    print("==========================================")
    print(f"Glacier: {GLACIER_NAME}")

    tile_paths = load_tile_paths()
    mask_paths = load_mask_paths(tile_paths)

    print(f"Tiles found: {len(tile_paths)}")

    # ---------------------------------------------------------
    # 1. Mosaic Sentinel-2 RGB source tiles
    # ---------------------------------------------------------
    print("\nMerging Sentinel-2 tiles...")

    srcs = [rasterio.open(p) for p in tile_paths]

    try:
        rgb_mosaic, transform = merge(srcs)
        profile = srcs[0].profile.copy()
    finally:
        for src in srcs:
            src.close()

    rgb = percentile_normalize(rgb_mosaic[:3])

    # ---------------------------------------------------------
    # 2. Mosaic U-Net masks
    # ---------------------------------------------------------
    print("Merging U-Net masks...")

    mask_srcs = [rasterio.open(p) for p in mask_paths]

    try:
        mask_mosaic, mask_transform = merge(
            mask_srcs,
            method="max"
        )
    finally:
        for src in mask_srcs:
            src.close()

    prediction_mask = mask_mosaic[0] > 0

    # Sanity check alignment.
    if (
        rgb.shape[:2] != prediction_mask.shape
        or abs(transform.a - mask_transform.a) > 0.1
        or abs(transform.e - mask_transform.e) > 0.1
    ):
        raise RuntimeError(
            "RGB mosaic and prediction mask are not spatially aligned."
        )

    # ---------------------------------------------------------
    # 3. Rasterize RGI geometry onto the same mosaic grid
    # ---------------------------------------------------------
    print("Loading RGI boundary...")

    geometry, glacier = get_rgi_geometry()

    geometry_gdf = gpd.GeoDataFrame(
        {"name": [GLACIER_NAME]},
        geometry=[geometry],
        crs="EPSG:4326",
    )

    # The Sentinel tiles are in their UTM CRS.
    target_crs = profile.get("crs")
    geometry_gdf = geometry_gdf.to_crs(target_crs)

    rgi_mask = rasterize(
        [(geometry_gdf.geometry.iloc[0], 1)],
        out_shape=prediction_mask.shape,
        transform=transform,
        fill=0,
        dtype="uint8",
    ).astype(bool)

    # ---------------------------------------------------------
    # 4. Save full RGB
    # ---------------------------------------------------------
    rgb_path = OUT_DIR / "baltoro_full_rgb.png"
    Image.fromarray(rgb).save(rgb_path)

    # ---------------------------------------------------------
    # 5. Save prediction overlay
    # ---------------------------------------------------------
    overlay = make_overlay(
        rgb,
        prediction_mask,
        rgi_mask,
    )

    overlay_path = OUT_DIR / "baltoro_prediction_overlay.png"
    overlay.save(overlay_path)

    # ---------------------------------------------------------
    # 6. Create RGI-vs-prediction diagnostic image
    # ---------------------------------------------------------
    diagnostic = np.zeros_like(rgb)

    # Background = RGB.
    diagnostic[:] = rgb

    # RGI interior gets a faint blue tint.
    diagnostic[rgi_mask] = (
        diagnostic[rgi_mask].astype(np.float32) * 0.65
        + np.array([0, 80, 255]) * 0.35
    ).astype(np.uint8)

    # Prediction gets a faint red tint.
    diagnostic[prediction_mask] = (
        diagnostic[prediction_mask].astype(np.float32) * 0.65
        + np.array([255, 40, 40]) * 0.35
    ).astype(np.uint8)

    # Agreement gets green.
    agreement = prediction_mask & rgi_mask
    diagnostic[agreement] = (
        diagnostic[agreement].astype(np.float32) * 0.55
        + np.array([0, 220, 80]) * 0.45
    ).astype(np.uint8)

    diagnostic_path = OUT_DIR / "baltoro_rgi_vs_prediction.png"
    Image.fromarray(diagnostic).save(diagnostic_path)

    # ---------------------------------------------------------
    # 7. Create side-by-side comparison
    # ---------------------------------------------------------
    rgb_img = Image.fromarray(rgb)
    overlay_img = overlay
    diagnostic_img = Image.fromarray(diagnostic)

    w, h = rgb_img.size

    comparison = Image.new(
        "RGB",
        (w * 3, h),
        "black",
    )

    comparison.paste(rgb_img, (0, 0))
    comparison.paste(overlay_img, (w, 0))
    comparison.paste(diagnostic_img, (w * 2, 0))

    comparison_path = OUT_DIR / "baltoro_comparison.png"
    comparison.save(comparison_path)

    # ---------------------------------------------------------
    # 8. Print useful statistics
    # ---------------------------------------------------------
    rgi_pixels = int(rgi_mask.sum())
    predicted_pixels = int(prediction_mask.sum())
    overlap_pixels = int((prediction_mask & rgi_mask).sum())

    pixel_area_m2 = abs(transform.a * transform.e)

    predicted_area_km2 = predicted_pixels * pixel_area_m2 / 1_000_000
    rgi_area_km2 = rgi_pixels * pixel_area_m2 / 1_000_000

    print("\n==========================================")
    print(" VISUAL COMPARISON COMPLETE")
    print("==========================================")
    print(f"RGI geometry pixels       : {rgi_pixels:,}")
    print(f"U-Net predicted pixels    : {predicted_pixels:,}")
    print(f"Overlap pixels             : {overlap_pixels:,}")
    print(f"RGI rasterized area        : {rgi_area_km2:.2f} km²")
    print(f"U-Net predicted area       : {predicted_area_km2:.2f} km²")
    print("\nOutputs:")
    print(f"RGB image                  : {rgb_path}")
    print(f"Prediction overlay         : {overlay_path}")
    print(f"RGI vs prediction          : {diagnostic_path}")
    print(f"Side-by-side comparison    : {comparison_path}")


if __name__ == "__main__":
    main()
