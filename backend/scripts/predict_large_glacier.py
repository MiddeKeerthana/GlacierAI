from pathlib import Path
import sys

import rasterio
from rasterio.merge import merge
import numpy as np

from pyproj import Transformer
from shapely.geometry import box, mapping
from shapely.ops import transform

# ==========================================================
# PROJECT ROOT
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT)
)

# ==========================================================
# PROJECT IMPORTS
# ==========================================================

from backend.app.services.rgi_service import (
    find_glacier_by_name,
)

from backend.app.services.sentinel_download import (
    download_sentinel_tile,
    get_utm_crs,
)

from backend.scripts.predict_geotiff import (
    predict_geotiff,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

TILE_SIZE_METERS = 20_000

DAYS_BACK = 60

PREDICTION_DIR = (
    PROJECT_ROOT
    / "datasets"
    / "live"
    / "predictions"
)

PREDICTION_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "datasets"
    / "live"
    / "large_glacier"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ==========================================================
# SAFE FILE NAME
# ==========================================================

def safe_name(name: str) -> str:

    return (
        name
        .lower()
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("-", "_")
    )


# ==========================================================
# FIND GLACIER
# ==========================================================

def get_glacier(glacier_name: str):

    print()
    print("Searching RGI...")
    print()

    glacier = find_glacier_by_name(
        query=glacier_name,
        limit=10,
    )

    if glacier is None:

        raise RuntimeError(
            f"Glacier not found: {glacier_name}"
        )

    if not glacier.get("geometry"):

        raise RuntimeError(
            "RGI glacier geometry was not returned."
        )

    return glacier


# ==========================================================
# TRANSFORM RGI GEOMETRY
# ==========================================================

def transform_geometry_to_utm(
    geometry,
    latitude,
    longitude,
):

    target_crs = get_utm_crs(
        latitude,
        longitude,
    )

    transformer = Transformer.from_crs(
        "EPSG:4326",
        target_crs,
        always_xy=True,
    )

    utm_geometry = transform(
        transformer.transform,
        geometry,
    )

    return (
        utm_geometry,
        target_crs,
    )


# ==========================================================
# CREATE 20 KM TILES
# ==========================================================

def create_tiles(
    glacier_geometry,
):

    min_x, min_y, max_x, max_y = (
        glacier_geometry.bounds
    )

    tiles = []

    x = min_x

    while x < max_x:

        y = min_y

        while y < max_y:

            tile = box(
                x,
                y,
                min(
                    x + TILE_SIZE_METERS,
                    max_x,
                ),
                min(
                    y + TILE_SIZE_METERS,
                    max_y,
                ),
            )

            if tile.intersects(
                glacier_geometry
            ):

                intersection = (
                    tile.intersection(
                        glacier_geometry
                    )
                )

                if not intersection.is_empty:

                    tiles.append(
                        {
                            "bbox": [
                                tile.bounds[0],
                                tile.bounds[1],
                                tile.bounds[2],
                                tile.bounds[3],
                            ],
                            "geometry": intersection,
                        }
                    )

            y += TILE_SIZE_METERS

        x += TILE_SIZE_METERS

    return tiles


# ==========================================================
# CONVERT TILE GEOMETRY BACK TO WGS84
# ==========================================================

def tile_geometry_to_wgs84(
    tile_geometry,
    target_crs,
):

    transformer = Transformer.from_crs(
        target_crs,
        "EPSG:4326",
        always_xy=True,
    )

    return transform(
        transformer.transform,
        tile_geometry,
    )


# ==========================================================
# GET EXPECTED MASK PATH
# ==========================================================

def get_mask_path(
    tile_name: str,
):

    return (
        PREDICTION_DIR
        / f"{tile_name}_glacier_mask.tif"
    )


# ==========================================================
# PROCESS ONE TILE
# ==========================================================

def process_tile(
    tile,
    tile_index,
    glacier,
    target_crs,
):

    glacier_name = glacier["name"]

    glacier_safe = safe_name(
        glacier_name
    )

    tile_name = (
        f"{glacier_safe}_tile_"
        f"{tile_index:03d}"
    )

    image_path = (
        PROJECT_ROOT
        / "datasets"
        / "live"
        / f"{tile_name}.tif"
    )

    mask_path = get_mask_path(
        tile_name
    )

    print()
    print("==========================================")
    print(
        f" PROCESSING TILE {tile_index}"
    )
    print("==========================================")
    print()

    # ======================================================
    # REUSE EXISTING MASK
    # ======================================================

    if mask_path.exists():

        print(
            "Existing prediction mask found."
        )

        print(
            "Reusing:",
            mask_path,
        )

        return {
            "mask": str(mask_path),
            "tile": tile_name,
            "reused": True,
        }

    # ======================================================
    # DOWNLOAD SENTINEL TILE
    # ======================================================

    print(
        "Downloading Sentinel-2 tile..."
    )

    download_result = (
        download_sentinel_tile(
            bbox=tile["bbox"],
            target_crs=target_crs,
            output_name=(
                f"{tile_name}.tif"
            ),
            days_back=DAYS_BACK,
        )
    )

    image_path = Path(
        download_result["path"]
    )

    # ======================================================
    # CONVERT TILE RGI GEOMETRY TO WGS84
    # ======================================================

    tile_geometry_wgs84 = (
        tile_geometry_to_wgs84(
            tile["geometry"],
            target_crs,
        )
    )

    tile_geojson = mapping(
        tile_geometry_wgs84
    )

    # ======================================================
    # U-NET INFERENCE
    # ======================================================

    print()
    print(
        "Running U-Net prediction..."
    )

    prediction_result = (
        predict_geotiff(
            image_path=str(
                image_path
            ),
            output_stem=tile_name,
            rgi_geometry=tile_geojson,
        )
    )

    # ======================================================
    # IMPORTANT:
    # predict_geotiff creates:
    #
    # *_glacier_mask.tif
    #
    # We use the actual generated file.
    # ======================================================

    mask_path = get_mask_path(
        tile_name
    )

    if not mask_path.exists():

        raise RuntimeError(
            "U-Net completed but the "
            f"mask was not found:\n{mask_path}"
        )

    print()
    print(
        "Tile prediction complete."
    )

    print(
        "Mask:",
        mask_path,
    )

    return {
        "mask": str(mask_path),
        "tile": tile_name,
        "reused": False,
    }


# ==========================================================
# MERGE MASKS
# ==========================================================

def merge_masks(
    prediction_results,
    glacier_name,
):

    mask_files = []

    for result in prediction_results:

        mask_path = result.get(
            "mask"
        )

        if not mask_path:
            continue

        path = Path(
            mask_path
        )

        if path.exists():

            mask_files.append(
                path
            )

    if not mask_files:

        raise RuntimeError(
            "No glacier mask files were found."
        )

    print()
    print("==========================================")
    print(" MERGING GLACIER MASKS")
    print("==========================================")
    print()

    print(
        "Masks found:",
        len(mask_files),
    )

    datasets = []

    try:

        for path in mask_files:

            print(
                "Loading:",
                path.name,
            )

            datasets.append(
                rasterio.open(path)
            )

        # --------------------------------------------------
        # MERGE
        # --------------------------------------------------

        mosaic, mosaic_transform = merge(
            datasets,
            method="max",
        )

        reference = datasets[0]

        output_path = (
            OUTPUT_DIR
            / (
                safe_name(
                    glacier_name
                )
                + "_full_mask.tif"
            )
        )

        profile = (
            reference.profile.copy()
        )

        profile.update(
            {
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": mosaic_transform,
                "count": 1,
                "dtype": "uint8",
                "compress": "lzw",
                "nodata": 0,
            }
        )

        # --------------------------------------------------
        # WRITE FINAL MASK
        # --------------------------------------------------

        with rasterio.open(
            output_path,
            "w",
            **profile,
        ) as dst:

            dst.write(
                mosaic[0].astype(
                    np.uint8
                ),
                1,
            )

        print()
        print(
            "Full glacier mask created:"
        )

        print(
            output_path
        )

        return output_path

    finally:

        for dataset in datasets:

            dataset.close()


# ==========================================================
# CALCULATE AREA
# ==========================================================

def calculate_area(
    mask_path,
):

    with rasterio.open(
        mask_path
    ) as src:

        mask = src.read(1)

        positive_pixels = int(
            np.count_nonzero(
                mask > 0
            )
        )

        pixel_width = abs(
            src.transform.a
        )

        pixel_height = abs(
            src.transform.e
        )

        pixel_area_m2 = (
            pixel_width
            * pixel_height
        )

        area_m2 = (
            positive_pixels
            * pixel_area_m2
        )

        area_km2 = (
            area_m2
            / 1_000_000
        )

    return (
        positive_pixels,
        area_m2,
        area_km2,
    )


# ==========================================================
# CREATE FINAL RGB/GLACIER OVERLAY
# ==========================================================

def create_final_overlay(
    glacier_name,
    mask_path,
):

    glacier_safe = safe_name(
        glacier_name
    )

    # ------------------------------------------------------
    # Find all tile RGB images
    # ------------------------------------------------------

    rgb_files = sorted(
        PREDICTION_DIR.glob(
            f"{glacier_safe}_tile_*_full_rgb.png"
        )
    )

    if not rgb_files:

        print(
            "No tile RGB images found."
        )

        return None

    print()
    print(
        "Tile RGB images available:",
        len(rgb_files),
    )

    # ------------------------------------------------------
    # Read final mask
    # ------------------------------------------------------

    with rasterio.open(
        mask_path
    ) as src:

        mask = src.read(1)

        transform_final = (
            src.transform
        )

        crs_final = src.crs

        width = src.width
        height = src.height

    # ------------------------------------------------------
    # For now, save a PNG version of
    # the final binary mask.
    # ------------------------------------------------------

    from PIL import Image

    mask_png_path = (
        OUTPUT_DIR
        / (
            glacier_safe
            + "_full_mask.png"
        )
    )

    mask_image = (
        (mask > 0)
        .astype(np.uint8)
        * 255
    )

    Image.fromarray(
        mask_image
    ).save(
        mask_png_path
    )

    print(
        "Final mask PNG:",
        mask_png_path,
    )

    return mask_png_path


# ==========================================================
# MAIN ANALYSIS
# ==========================================================

def analyze_large_glacier(
    glacier_name: str,
):

    print()
    print("==========================================")
    print(" GLACIERAI - FULL GLACIER ANALYSIS")
    print("==========================================")
    print()

    # ======================================================
    # RGI
    # ======================================================

    glacier = get_glacier(
        glacier_name
    )

    print(
        "Glacier       :",
        glacier["name"],
    )

    print(
        "RGI ID        :",
        glacier["rgi_id"],
    )

    print(
        "Inventory area:",
        glacier.get(
            "area_km2"
        ),
        "km²",
    )

    print(
        "Latitude      :",
        glacier["latitude"],
    )

    print(
        "Longitude     :",
        glacier["longitude"],
    )

    # ======================================================
    # UTM GEOMETRY
    # ======================================================

    utm_geometry, target_crs = (
        transform_geometry_to_utm(
            glacier["geometry"],
            glacier["latitude"],
            glacier["longitude"],
        )
    )

    print(
        "Target CRS    :",
        target_crs,
    )

    print(
        "Glacier bounds:",
        utm_geometry.bounds,
    )

    # ======================================================
    # CREATE TILES
    # ======================================================

    tiles = create_tiles(
        utm_geometry
    )

    print()
    print(
        "Tiles required:",
        len(tiles),
    )

    print(
        "Tile size     :",
        TILE_SIZE_METERS,
        "m",
    )

    print()

    if not tiles:

        raise RuntimeError(
            "No tiles intersect the glacier."
        )

    # ======================================================
    # PROCESS TILES
    # ======================================================

    prediction_results = []

    for index, tile in enumerate(
        tiles,
        start=1,
    ):

        try:

            result = process_tile(
                tile=tile,
                tile_index=index,
                glacier=glacier,
                target_crs=target_crs,
            )

            prediction_results.append(
                result
            )

        except Exception as error:

            print()
            print(
                f"Tile {index} failed:"
            )

            print(
                str(error)
            )

            print(
                "Continuing..."
            )

    # ======================================================
    # CHECK
    # ======================================================

    if not prediction_results:

        raise RuntimeError(
            "No tile predictions were available."
        )

    # ======================================================
    # MERGE
    # ======================================================

    full_mask = merge_masks(
        prediction_results,
        glacier["name"],
    )

    # ======================================================
    # AREA
    # ======================================================

    pixels, area_m2, area_km2 = (
        calculate_area(
            full_mask
        )
    )

    # ======================================================
    # FINAL VISUALIZATION
    # ======================================================

    final_mask_png = (
        create_final_overlay(
            glacier_name=glacier["name"],
            mask_path=full_mask,
        )
    )

    # ======================================================
    # FINAL RESULT
    # ======================================================

    print()
    print("==========================================")
    print(" FINAL GLACIER RESULT")
    print("==========================================")
    print()

    print(
        "Glacier          :",
        glacier["name"],
    )

    print(
        "RGI ID           :",
        glacier["rgi_id"],
    )

    print(
        "RGI inventory    :",
        glacier.get(
            "area_km2"
        ),
        "km²",
    )

    print(
        "Predicted pixels :",
        pixels,
    )

    print(
        "Predicted area   :",
        round(
            area_km2,
            4,
        ),
        "km²",
    )

    print(
        "Predicted area   :",
        round(
            area_m2,
            2,
        ),
        "m²",
    )

    print(
        "Tiles processed  :",
        len(
            prediction_results
        ),
        "/",
        len(tiles),
    )

    print(
        "Full mask        :",
        full_mask,
    )

    if final_mask_png:

        print(
            "Final mask PNG   :",
            final_mask_png,
        )

    print()

    return {
        "glacier":
            glacier["name"],

        "rgi_id":
            glacier["rgi_id"],

        "rgi_area_km2":
            glacier.get(
                "area_km2"
            ),

        "predicted_area_km2":
            area_km2,

        "predicted_area_m2":
            area_m2,

        "predicted_pixels":
            pixels,

        "tiles_total":
            len(tiles),

        "tiles_processed":
            len(
                prediction_results
            ),

        "mask":
            str(full_mask),

        "mask_png":
            str(final_mask_png)
            if final_mask_png
            else None,
    }


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    # Change this name when testing another glacier.
    glacier_name = "Baltoro Glacier"

    try:

        result = analyze_large_glacier(
            glacier_name
        )

        print()
        print(
            "=========================================="
        )

        print(
            " FULL ANALYSIS COMPLETED"
        )

        print(
            "=========================================="
        )

        print()

        print(result)

    except Exception as error:

        print()
        print(
            "=========================================="
        )

        print(
            " FULL ANALYSIS FAILED"
        )

        print(
            "=========================================="
        )

        print()

        print(
            "Error:",
            error,
        )