from pathlib import Path
import argparse
import sys

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
    print(
        "Install packages with:\n"
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

# NEW DATASET — DOES NOT TOUCH THE OLD ONE
OUTPUT_ROOT = (
    PROJECT_DIR
    / "datasets"
    / "classification_context"
)

MANIFEST_PATH = OUTPUT_ROOT / "context_dataset_manifest.csv"


# ============================================================
# CONFIGURATION
# ============================================================

IMAGE_SIZE = 224

# Larger surrounding area than the original 20%
BBOX_PADDING = 0.50

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
# HELPERS
# ============================================================

def clean_class_name(value):
    return str(value).strip().lower().replace(" ", "_")


def normalize_rgi_id(value):
    return str(value).strip()


def normalize_to_uint8(array):
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

    scaled = np.clip(
        scaled,
        0.0,
        1.0
    )

    return (scaled * 255.0).astype(np.uint8)


def padded_bounds(geometry):

    minx, miny, maxx, maxy = geometry.bounds

    width = max(
        maxx - minx,
        0.0001
    )

    height = max(
        maxy - miny,
        0.0001
    )

    px = width * BBOX_PADDING
    py = height * BBOX_PADDING

    return (
        minx - px,
        miny - py,
        maxx + px,
        maxy + py,
    )


# ============================================================
# LOAD METADATA
# ============================================================

def load_metadata():

    df = pd.read_csv(
        METADATA_PATH
    )

    required = [
        "rgi_id",
        "glac_name",
        "class_name",
        "area_km2",
        "cenlat",
        "cenlon",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing metadata columns: {missing}"
        )

    df["rgi_id"] = df[
        "rgi_id"
    ].map(normalize_rgi_id)

    df["class_name"] = df[
        "class_name"
    ].map(clean_class_name)

    unknown = sorted(
        set(df["class_name"])
        - VALID_CLASSES
    )

    if unknown:
        raise ValueError(
            f"Unknown classes: {unknown}"
        )

    return (
        df
        .drop_duplicates(
            subset=["rgi_id"]
        )
        .reset_index(drop=True)
    )


# ============================================================
# LOAD RGI
# ============================================================

def load_rgi():

    print("\nLoading RGI...")

    rgi = gpd.read_file(
        RGI_PATH
    )

    rgi["rgi_id"] = rgi[
        "rgi_id"
    ].map(normalize_rgi_id)

    return rgi.to_crs(
        "EPSG:4326"
    )


# --------------------------------------------------------
# Split
# --------------------------------------------------------

def split_records(df):
    from sklearn.model_selection import train_test_split

    # First: 80% train, 20% temporary
    train_df, temp_df = train_test_split(
        df,
        test_size=0.20,
        stratify=df["class_name"],
        random_state=RANDOM_SEED,
    )

    # Then split the remaining 20% equally into validation and test
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        stratify=temp_df["class_name"],
        random_state=RANDOM_SEED,
    )

    train_df = train_df.copy()
    val_df = val_df.copy()
    test_df = test_df.copy()

    train_df["split"] = "train"
    val_df["split"] = "val"
    test_df["split"] = "test"

    return pd.concat(
        [train_df, val_df, test_df],
        ignore_index=True,
    )


# ============================================================
# SENTINEL SEARCH
# ============================================================

def search_best_scene(
    catalog,
    glacier_geometry,
    max_cloud,
):

    search_geometry = box(
        *padded_bounds(
            glacier_geometry
        )
    )

    search = catalog.search(
        collections=[
            "sentinel-2-l2a"
        ],
        intersects=mapping(
            search_geometry
        ),
        datetime=(
            f"{DATE_START}/{DATE_END}"
        ),
        query={
            "eo:cloud_cover": {
                "lte": max_cloud
            }
        },
        max_items=50,
    )

    items = list(
        search.items()
    )

    if not items:
        return None

    intersecting = []

    for item in items:

        if item.geometry is None:
            continue

        try:

            scene_geometry = shape(
                item.geometry
            )

            if scene_geometry.intersects(
                glacier_geometry
            ):
                intersecting.append(
                    item
                )

        except Exception:
            continue

    candidates = (
        intersecting
        or items
    )

    def cloud_score(item):

        try:
            return float(
                item.properties.get(
                    "eo:cloud_cover",
                    100
                )
            )
        except Exception:
            return 100

    candidates.sort(
        key=cloud_score
    )

    return candidates[0]


# ============================================================
# READ SENTINEL BAND
# ============================================================

def read_asset_crop(
    href,
    target_bounds_wgs84,
    glacier_geometry_wgs84,
):

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

        window = (
            window
            .round_offsets()
            .round_lengths()
        )

        full_window = (
            rasterio.windows.Window(
                0,
                0,
                src.width,
                src.height,
            )
        )

        window = window.intersection(
            full_window
        )

        if (
            window.width <= 0
            or window.height <= 0
        ):
            raise ValueError(
                "Crop is outside Sentinel scene."
            )

        data = src.read(
            1,
            window=window,
            out_shape=(
                IMAGE_SIZE,
                IMAGE_SIZE,
            ),
            resampling=Resampling.bilinear,
        )

        crop_transform = (
            src.window_transform(
                window
            )
        )

        glacier_geometry_src = (
            rasterio.warp.transform_geom(
                "EPSG:4326",
                src.crs,
                mapping(
                    glacier_geometry_wgs84
                ),
                precision=6,
            )
        )

        scale_x = (
            window.width
            / IMAGE_SIZE
        )

        scale_y = (
            window.height
            / IMAGE_SIZE
        )

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
            out_shape=(
                IMAGE_SIZE,
                IMAGE_SIZE,
            ),
            transform=output_transform,
            invert=True,
        )

        return (
            normalize_to_uint8(data),
            mask,
        )


# ============================================================
# BUILD CONTEXT RGB
# ============================================================

def build_context_rgb(
    item,
    glacier_geometry,
):

    bounds = padded_bounds(
        glacier_geometry
    )

    assets = {}

    for band in [
        RED_ASSET,
        GREEN_ASSET,
        BLUE_ASSET,
    ]:

        asset = item.assets.get(
            band
        )

        if asset is None:
            raise ValueError(
                f"Missing Sentinel asset: {band}"
            )

        assets[band] = asset.href

    red, mask = read_asset_crop(
        assets[RED_ASSET],
        bounds,
        glacier_geometry,
    )

    green, _ = read_asset_crop(
        assets[GREEN_ASSET],
        bounds,
        glacier_geometry,
    )

    blue, _ = read_asset_crop(
        assets[BLUE_ASSET],
        bounds,
        glacier_geometry,
    )

    rgb = np.stack(
        [
            red,
            green,
            blue,
        ],
        axis=-1,
    )

    # IMPORTANT:
    # DO NOT BLACK OUT SURROUNDING TERRAIN.
    #
    # The original classifier used:
    # rgb[~mask] = 0
    #
    # We intentionally remove that operation.

    return rgb, mask


# ============================================================
# SAVE
# ============================================================

def save_image(
    rgb,
    output_path,
):

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

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--max-cloud",
        type=float,
        default=DEFAULT_MAX_CLOUD,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    print("=" * 70)
    print(
        "GLACIERAI - CONTEXT CLASSIFICATION DATASET"
    )
    print("=" * 70)

    print(
        "Output:",
        OUTPUT_ROOT
    )

    print(
        "Image size:",
        IMAGE_SIZE
    )

    print(
        "Context padding:",
        BBOX_PADDING
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    df = load_metadata()

    print(
        "\nClassification records:",
        len(df)
    )

    # --------------------------------------------------------
    # RGI
    # --------------------------------------------------------

    rgi = load_rgi()

    rgi_lookup = {
        row.rgi_id: row.geometry
        for row in rgi[
            [
                "rgi_id",
                "geometry",
            ]
        ].itertuples()
    }

    missing = [
        rid
        for rid in df["rgi_id"]
        if rid not in rgi_lookup
    ]

    if missing:

        raise RuntimeError(
            f"Missing RGI polygons: {missing}"
        )

    # --------------------------------------------------------
    # Split
    # --------------------------------------------------------

    split_df = split_records(
        df
    )

    print("\nSplit distribution:")

    print(
        split_df
        .groupby(
            [
                "split",
                "class_name",
            ]
        )
        .size()
        .unstack(
            fill_value=0
        )
    )


    # For --limit tests, limit AFTER stratified splitting so that
    # For small test runs, choose records across classes instead of
    # simply taking the first N rows. This guarantees that --limit 3
    # tests all three glacier classes.
    if args.limit is not None:

        if args.limit >= len(VALID_CLASSES):
            selected_parts = []

            for class_name in sorted(VALID_CLASSES):
                class_rows = split_df[
                    split_df["class_name"] == class_name
                ]

                if not class_rows.empty:
                    selected_parts.append(
                        class_rows.iloc[[0]]
                    )

            selected = pd.concat(
                selected_parts,
                ignore_index=True,
            )

            if args.limit > len(selected):
                selected_indices = set(
                    selected["rgi_id"]
                )

                remaining = split_df[
                    ~split_df["rgi_id"].isin(
                        selected_indices
                    )
                ]

                extra = remaining.head(
                    args.limit - len(selected)
                )

                split_df = pd.concat(
                    [selected, extra],
                    ignore_index=True,
                )
            else:
                split_df = selected.head(
                    args.limit
                ).copy()

        else:
            split_df = split_df.head(
                args.limit
            ).copy()

        print(
            f"\nTEST MODE: processing only {len(split_df)} records."
        )

        print(
            "Test classes:",
            sorted(
                split_df["class_name"].unique()
            )
        )

    # --------------------------------------------------------
    # Output folders
    # --------------------------------------------------------

    for split in [
        "train",
        "val",
        "test",
    ]:

        for class_name in sorted(
            VALID_CLASSES
        ):

            (
                OUTPUT_ROOT
                / split
                / class_name
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

    # --------------------------------------------------------
    # Sentinel
    # --------------------------------------------------------

    print(
        "\nConnecting to Sentinel-2..."
    )

    catalog = (
        pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1/",
            modifier=planetary_computer.sign_inplace,
        )
    )

    print(
        "STAC connection ready."
    )

    manifest_rows = []

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    total = len(split_df)

    for index, row in split_df.iterrows():

        rgi_id = row["rgi_id"]
        glacier_name = row["glac_name"]
        class_name = row["class_name"]
        split = row["split"]

        print(
            f"\n[{index + 1}/{total}] "
            f"{glacier_name}"
        )

        print(
            "RGI:",
            rgi_id
        )

        print(
            "Class:",
            class_name
        )

        print(
            "Split:",
            split
        )

        glacier_geometry = (
            rgi_lookup[rgi_id]
        )

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

        if (
            output_path.exists()
            and not args.overwrite
        ):

            print(
                "Already exists:",
                output_path.name
            )

            continue

        try:

            item = search_best_scene(
                catalog,
                glacier_geometry,
                args.max_cloud,
            )

            if item is None:

                print(
                    "No suitable scene."
                )

                continue

            cloud = item.properties.get(
                "eo:cloud_cover"
            )

            print(
                "Scene:",
                item.id
            )

            print(
                "Cloud:",
                cloud,
                "%"
            )

            rgb, glacier_mask = (
                build_context_rgb(
                    item,
                    glacier_geometry,
                )
            )

            glacier_pixels = int(
                glacier_mask.sum()
            )

            glacier_fraction = (
                glacier_pixels
                / float(
                    IMAGE_SIZE
                    * IMAGE_SIZE
                )
            )

            if glacier_pixels == 0:

                print(
                    "Empty glacier mask."
                )

                continue

            save_image(
                rgb,
                output_path,
            )

            print(
                "Saved:",
                output_path
            )

            print(
                "Glacier pixels:",
                glacier_pixels,
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
                    output_path.relative_to(
                        PROJECT_DIR
                    )
                ),
                "image_size": IMAGE_SIZE,
                "glacier_pixels": glacier_pixels,
                "glacier_fraction": glacier_fraction,
                "status": "success",
            })

        except Exception as exc:

            print(
                "ERROR:",
                exc
            )

    # --------------------------------------------------------
    # Manifest
    # --------------------------------------------------------

    manifest = pd.DataFrame(
        manifest_rows
    )

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest.to_csv(
        MANIFEST_PATH,
        index=False,
    )

    print("\n" + "=" * 70)
    print(
        "CONTEXT DATASET PREPARATION COMPLETE"
    )
    print("=" * 70)

    if not manifest.empty:

        print(
            "\nStatus:"
        )

        print(
            manifest[
                "status"
            ].value_counts()
        )

        print(
            "\nImages:",
            len(manifest)
        )

    print(
        "\nManifest:",
        MANIFEST_PATH
    )


if __name__ == "__main__":
    main()