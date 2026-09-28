"""
GlacierAI - CNN Classification Dataset Preparation

Run from the GlacierAI project root:
    python backend/scripts/prepare_classifier_dataset.py

Test a small batch first:
    python backend/scripts/prepare_classifier_dataset.py --limit 3

Full dataset:
    python backend/scripts/prepare_classifier_dataset.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, transform_bounds
from shapely.geometry import box, mapping, shape

try:
    import planetary_computer
    import pystac_client
except ImportError:
    print("Missing packages. Install with:")
    print(
        "pip install pystac-client planetary-computer "
        "rasterio geopandas shapely pillow pandas scikit-learn"
    )
    sys.exit(1)


# ============================================================
# PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]

METADATA_PATH = (
    PROJECT_DIR
    / "datasets"
    / "classification"
    / "classification_metadata.csv"
)

RGI_PATH = (
    PROJECT_DIR
    / "datasets"
    / "processed"
    / "global_rgi.gpkg"
)

OUTPUT_ROOT = (
    PROJECT_DIR
    / "datasets"
    / "classification"
)

MANIFEST_PATH = OUTPUT_ROOT / "prepared_dataset_manifest.csv"

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/"
SENTINEL_COLLECTION = "sentinel-2-l2a"


# ============================================================
# CONFIGURATION
# ============================================================

IMAGE_SIZE = 224
BBOX_PADDING = 0.20

DEFAULT_MAX_CLOUD = 30.0

DATE_START = "2018-01-01"
DATE_END = "2026-12-31"

RANDOM_SEED = 42

RED_ASSET = "B04"
GREEN_ASSET = "B03"
BLUE_ASSET = "B02"

VALID_CLASSES = {
    "ice_cap",
    "mountain_glacier",
    "glacieret_snowfield",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def print_header(max_cloud: float):
    print("=" * 70)
    print("GLACIERAI - CNN CLASSIFICATION DATASET PREPARATION")
    print("=" * 70)
    print(f"Metadata         : {METADATA_PATH}")
    print(f"RGI database     : {RGI_PATH}")
    print(f"Output           : {OUTPUT_ROOT}")
    print(f"Image size       : {IMAGE_SIZE} x {IMAGE_SIZE}")
    print(f"Maximum cloud    : {max_cloud}%")
    print(f"Sentinel period  : {DATE_START} to {DATE_END}")
    print("=" * 70)


def clean_class_name(value) -> str:
    return str(value).strip().lower().replace(" ", "_")


def normalize_to_uint8(array: np.ndarray) -> np.ndarray:
    """
    Convert Sentinel-2 reflectance values into 8-bit image values.
    Percentile clipping makes the RGB chips suitable for CNN input.
    """
    array = array.astype(np.float32)

    finite = np.isfinite(array)

    if not finite.any():
        return np.zeros(array.shape, dtype=np.uint8)

    values = array[finite]

    lo = float(np.percentile(values, 1))
    hi = float(np.percentile(values, 99))

    if hi <= lo:
        lo = float(values.min())
        hi = float(values.max())

    if hi <= lo:
        return np.zeros(array.shape, dtype=np.uint8)

    scaled = (array - lo) / (hi - lo)
    scaled = np.clip(scaled, 0.0, 1.0)

    return (scaled * 255.0).astype(np.uint8)


def padded_bounds(geometry):
    minx, miny, maxx, maxy = geometry.bounds

    width = max(maxx - minx, 0.0001)
    height = max(maxy - miny, 0.0001)

    px = width * BBOX_PADDING
    py = height * BBOX_PADDING

    return (
        minx - px,
        miny - py,
        maxx + px,
        maxy + py,
    )


def normalize_rgi_id(value) -> str:
    return str(value).strip()


# ============================================================
# METADATA / RGI
# ============================================================

def load_metadata() -> pd.DataFrame:
    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata file not found:\n{METADATA_PATH}"
        )

    df = pd.read_csv(METADATA_PATH)

    required = [
        "rgi_id",
        "glac_name",
        "primeclass",
        "class_name",
        "area_km2",
        "cenlat",
        "cenlon",
    ]

    missing = [column for column in required if column not in df.columns]

    if missing:
        raise ValueError(
            f"Metadata is missing columns: {missing}"
        )

    df["rgi_id"] = df["rgi_id"].map(normalize_rgi_id)
    df["class_name"] = df["class_name"].map(clean_class_name)

    unknown = sorted(set(df["class_name"]) - VALID_CLASSES)

    if unknown:
        raise ValueError(
            f"Unknown classes: {unknown}\n"
            f"Expected: {sorted(VALID_CLASSES)}"
        )

    df = (
        df
        .drop_duplicates(subset=["rgi_id"])
        .reset_index(drop=True)
    )

    return df


def load_rgi() -> gpd.GeoDataFrame:
    if not RGI_PATH.exists():
        raise FileNotFoundError(
            f"RGI database not found:\n{RGI_PATH}"
        )

    print("\nLoading global RGI database...")

    rgi = gpd.read_file(RGI_PATH)

    if "rgi_id" not in rgi.columns:
        raise ValueError(
            "global_rgi.gpkg does not contain rgi_id."
        )

    if rgi.crs is None:
        raise ValueError(
            "global_rgi.gpkg has no CRS."
        )

    rgi["rgi_id"] = rgi["rgi_id"].map(normalize_rgi_id)

    return rgi.to_crs("EPSG:4326")



def split_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Split the classification dataset.

    For the normal 220-record dataset, use stratified train/val/test
    splitting so all three glacier classes are represented.

    For a small --limit test, do not stratify. The test records are
    placed in the test split so the Sentinel-2 extraction can be checked.
    """
    from sklearn.model_selection import train_test_split

    # Small test runs such as --limit 3 cannot be stratified because
    # there may be fewer than 2 samples in a class.
    if len(df) < 15 or df["class_name"].value_counts().min() < 2:
        test_df = df.copy()
        test_df["split"] = "test"
        return test_df.reset_index(drop=True)

    train_df, temp_df = train_test_split(
        df,
        test_size=0.20,
        random_state=RANDOM_SEED,
        stratify=df["class_name"],
    )

    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        random_state=RANDOM_SEED,
        stratify=temp_df["class_name"],
    )

    train_df = train_df.copy()
    val_df = val_df.copy()
    test_df = test_df.copy()

    train_df["split"] = "train"
    val_df["split"] = "val"
    test_df["split"] = "test"

    return (
        pd.concat(
            [train_df, val_df, test_df],
            ignore_index=True,
        )
        .sample(
            frac=1,
            random_state=RANDOM_SEED,
        )
        .reset_index(drop=True)
    )

# ============================================================
# SENTINEL-2 SEARCH
# ============================================================

def search_best_scene(catalog, glacier_geometry, max_cloud):
    """
    Find a Sentinel-2 L2A scene intersecting the RGI glacier.

    Candidate selection prioritizes:
      - actual glacier intersection
      - low cloud percentage
    """
    search_geometry = box(*padded_bounds(glacier_geometry))

    search = catalog.search(
        collections=[SENTINEL_COLLECTION],
        intersects=mapping(search_geometry),
        datetime=f"{DATE_START}/{DATE_END}",
        query={
            "eo:cloud_cover": {
                "lte": max_cloud
            }
        },
        max_items=50,
    )

    items = list(search.items())

    if not items:
        return None, 0

    intersecting = []

    for item in items:
        if item.geometry is None:
            continue

        try:
            scene_geometry = shape(item.geometry)

            if scene_geometry.intersects(glacier_geometry):
                intersecting.append(item)
        except Exception:
            continue

    candidates = intersecting or items

    def score(item):
        cloud = item.properties.get(
            "eo:cloud_cover",
            100.0,
        )

        try:
            cloud = float(cloud)
        except Exception:
            cloud = 100.0

        # Lower score is better.
        return cloud

    candidates.sort(key=score)

    return candidates[0], len(items)


# ============================================================
# SENTINEL-2 IMAGE EXTRACTION
# ============================================================

def read_asset_crop(
    href: str,
    target_bounds_wgs84,
    glacier_geometry_wgs84,
    output_size: int,
):
    """
    Read only the required spatial window from a Sentinel-2 asset.
    """
    with rasterio.open(href) as src:
        bounds_src = transform_bounds(
            "EPSG:4326",
            src.crs,
            *target_bounds_wgs84,
            densify_pts=21,
        )

        window = rasterio.windows.from_bounds(
            *bounds_src,
            transform=src.transform,
        )

        window = window.round_offsets().round_lengths()

        full_window = rasterio.windows.Window(
            0,
            0,
            src.width,
            src.height,
        )

        window = window.intersection(full_window)

        if window.width <= 0 or window.height <= 0:
            raise ValueError(
                "Requested glacier crop lies outside the Sentinel-2 scene."
            )

        data = src.read(
            1,
            window=window,
            out_shape=(output_size, output_size),
            resampling=Resampling.bilinear,
        )

        crop_transform = src.window_transform(window)

        glacier_geometry_src = rasterio.warp.transform_geom(
            "EPSG:4326",
            src.crs,
            mapping(glacier_geometry_wgs84),
            precision=6,
        )

        mask = geometry_mask(
            [glacier_geometry_src],
            out_shape=(output_size, output_size),
            transform=crop_transform,
            invert=True,
        )

        # crop_transform describes the original window size. Rasterio's
        # read out_shape scales it automatically for the output grid.
        scale_x = window.width / output_size
        scale_y = window.height / output_size

        output_transform = rasterio.Affine(
            crop_transform.a * scale_x,
            crop_transform.b,
            crop_transform.c,
            crop_transform.d,
            crop_transform.e * scale_y,
            crop_transform.f,
        )

        mask = geometry_mask(
            [glacier_geometry_src],
            out_shape=(output_size, output_size),
            transform=output_transform,
            invert=True,
        )

        return normalize_to_uint8(data), mask


def asset_href(item, name):
    asset = item.assets.get(name)

    if asset is None:
        return None

    return asset.href


def build_rgb_image(item, glacier_geometry):
    bounds = padded_bounds(glacier_geometry)

    red_href = asset_href(item, RED_ASSET)
    green_href = asset_href(item, GREEN_ASSET)
    blue_href = asset_href(item, BLUE_ASSET)

    missing = [
        name
        for name, href in [
            (RED_ASSET, red_href),
            (GREEN_ASSET, green_href),
            (BLUE_ASSET, blue_href),
        ]
        if not href
    ]

    if missing:
        raise ValueError(
            f"Scene {item.id} is missing assets: {missing}"
        )

    red, mask = read_asset_crop(
        red_href,
        bounds,
        glacier_geometry,
        IMAGE_SIZE,
    )

    green, _ = read_asset_crop(
        green_href,
        bounds,
        glacier_geometry,
        IMAGE_SIZE,
    )

    blue, _ = read_asset_crop(
        blue_href,
        bounds,
        glacier_geometry,
        IMAGE_SIZE,
    )

    rgb = np.stack(
        [red, green, blue],
        axis=-1,
    )

    # Mask the outside of the RGI glacier.
    rgb[~mask] = 0

    return rgb, mask


def save_image(rgb: np.ndarray, output_path: Path):
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    Image.fromarray(
        rgb,
        mode="RGB",
    ).save(
        output_path,
        quality=95,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Prepare Sentinel-2 glacier-type CNN dataset."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N records.",
    )

    parser.add_argument(
        "--max-cloud",
        type=float,
        default=DEFAULT_MAX_CLOUD,
        help="Maximum scene cloud percentage.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate images that already exist.",
    )

    args = parser.parse_args()

    print_header(args.max_cloud)

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    df = load_metadata()

    print(f"\nClassification records: {len(df)}")

    print("\nClass distribution:")
    print(df["class_name"].value_counts())

    if args.limit is not None:
        df = df.head(args.limit).copy()
        print(
            f"\nTEST MODE: processing only {len(df)} records."
        )

    # --------------------------------------------------------
    # RGI
    # --------------------------------------------------------

    rgi = load_rgi()

    rgi_lookup = {
        row.rgi_id: row.geometry
        for row in rgi[
            ["rgi_id", "geometry"]
        ].itertuples()
    }

    missing_rgi = [
        rid
        for rid in df["rgi_id"]
        if rid not in rgi_lookup
    ]

    print(f"\nMatching RGI polygons: {len(df) - len(missing_rgi)}")
    print(f"Missing polygons     : {len(missing_rgi)}")

    if missing_rgi:
        for rid in missing_rgi:
            print("  ", rid)

        raise RuntimeError(
            "Some classification records have no matching RGI polygon."
        )

    # --------------------------------------------------------
    # Split
    # --------------------------------------------------------

    split_df = split_records(df)

    print("\nSplit distribution:")
    print(
        split_df
        .groupby(["split", "class_name"])
        .size()
        .unstack(fill_value=0)
    )

    # --------------------------------------------------------
    # Output folders
    # --------------------------------------------------------

    for split in ["train", "val", "test"]:
        for class_name in sorted(VALID_CLASSES):
            (
                OUTPUT_ROOT
                / split
                / class_name
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

    # --------------------------------------------------------
    # STAC
    # --------------------------------------------------------

    print("\nConnecting to Sentinel-2 STAC catalog...")

    catalog = pystac_client.Client.open(
        STAC_URL,
        modifier=planetary_computer.sign_inplace,
    )

    print("STAC connection ready.")

    manifest_rows = []

    # --------------------------------------------------------
    # Process records
    # --------------------------------------------------------

    total = len(split_df)

    for index, row in split_df.iterrows():
        rgi_id = row["rgi_id"]
        glacier_name = row["glac_name"]
        class_name = row["class_name"]
        split = row["split"]

        print("\n" + "-" * 70)
        print(f"[{index + 1}/{total}] {glacier_name}")
        print(f"RGI   : {rgi_id}")
        print(f"Class : {class_name}")
        print(f"Split : {split}")

        glacier_geometry = rgi_lookup[rgi_id]

        safe_id = (
            rgi_id
            .lower()
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
        )

        output_path = (
            OUTPUT_ROOT
            / split
            / class_name
            / f"{safe_id}.jpg"
        )

        if output_path.exists() and not args.overwrite:
            print("Already exists:", output_path.name)

            manifest_rows.append({
                "rgi_id": rgi_id,
                "glac_name": glacier_name,
                "class_name": class_name,
                "split": split,
                "image_path": str(
                    output_path.relative_to(PROJECT_DIR)
                ),
                "status": "already_exists",
            })

            continue

        try:
            item, candidate_count = search_best_scene(
                catalog,
                glacier_geometry,
                args.max_cloud,
            )

            if item is None:
                print("No suitable Sentinel-2 scene found.")

                manifest_rows.append({
                    "rgi_id": rgi_id,
                    "glac_name": glacier_name,
                    "class_name": class_name,
                    "split": split,
                    "status": "no_scene",
                })

                continue

            cloud = item.properties.get(
                "eo:cloud_cover"
            )

            print("Scene :", item.id)
            print("Cloud :", cloud, "%")
            print("Candidates:", candidate_count)

            rgb, glacier_mask = build_rgb_image(
                item,
                glacier_geometry,
            )

            glacier_pixels = int(glacier_mask.sum())
            glacier_fraction = (
                glacier_pixels
                / float(IMAGE_SIZE * IMAGE_SIZE)
            )

            if glacier_pixels == 0:
                print("Empty glacier mask; skipping.")

                manifest_rows.append({
                    "rgi_id": rgi_id,
                    "glac_name": glacier_name,
                    "class_name": class_name,
                    "split": split,
                    "scene_id": item.id,
                    "cloud_cover": cloud,
                    "status": "empty_mask",
                })

                continue

            save_image(
                rgb,
                output_path,
            )

            print(
                "Saved:",
                output_path.relative_to(PROJECT_DIR),
            )

            print(
                f"Glacier pixels: {glacier_pixels} "
                f"({glacier_fraction * 100:.1f}%)"
            )

            manifest_rows.append({
                "rgi_id": rgi_id,
                "glac_name": glacier_name,
                "class_name": class_name,
                "split": split,
                "scene_id": item.id,
                "scene_datetime": (
                    item.datetime.isoformat()
                    if item.datetime
                    else ""
                ),
                "cloud_cover": cloud,
                "image_path": str(
                    output_path.relative_to(PROJECT_DIR)
                ),
                "image_size": IMAGE_SIZE,
                "glacier_pixels": glacier_pixels,
                "glacier_fraction": glacier_fraction,
                "status": "success",
            })

        except Exception as exc:
            print("ERROR:", exc)

            manifest_rows.append({
                "rgi_id": rgi_id,
                "glac_name": glacier_name,
                "class_name": class_name,
                "split": split,
                "status": "error",
                "error": str(exc),
            })

    # --------------------------------------------------------
    # Manifest
    # --------------------------------------------------------

    manifest = pd.DataFrame(manifest_rows)

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest.to_csv(
        MANIFEST_PATH,
        index=False,
    )

    print("\n" + "=" * 70)
    print("DATASET PREPARATION COMPLETE")
    print("=" * 70)

    if not manifest.empty:
        print("\nStatus:")
        print(manifest["status"].value_counts())

        usable = manifest[
            manifest["status"].isin(
                ["success", "already_exists"]
            )
        ]

        print(f"\nUsable images: {len(usable)}")

        if not usable.empty:
            print("\nUsable images by split/class:")
            print(
                usable
                .groupby(["split", "class_name"])
                .size()
                .unstack(fill_value=0)
            )

    print("\nManifest:")
    print(MANIFEST_PATH)

    print("\nDo NOT train yet if many images failed.")
    print("First inspect the dataset counts and a few image crops.")


if __name__ == "__main__":
    main()
