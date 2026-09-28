from pathlib import Path
import os

import cv2
import numpy as np
import rasterio
import torch

from rasterio.features import rasterize
from rasterio.warp import transform_geom

from backend.models.unet import UNet


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "checkpoints"
    / "best_unet_v3.pth"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "datasets"
    / "live"
    / "predictions"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

PATCH_SIZE = 256
STRIDE = 128

# Base probability threshold.  We keep the trained-model threshold at 0.20,
# but use a confidence-aware post-processing step below instead of blindly
# accepting every pixel above this value.
THRESHOLD = 0.20

# High-confidence "seed" pixels used to preserve small/fragmented glaciers
# without allowing large low-confidence regions to become glacier.
CORE_THRESHOLD = 0.50

# Very small components can be single-pixel noise.  Four 10 m pixels are
# only 0.0004 km², so this is intentionally conservative.
MIN_COMPONENT_PIXELS = 4

# A standalone candidate component can be retained when its mean probability
# is strong enough, even if it has no CORE_THRESHOLD pixel.
MIN_COMPONENT_MEAN_PROBABILITY = 0.30

# Conservative morphological refinement.
# Closing reconnects very small gaps inside predicted glacier regions.
# Opening removes isolated speckle noise. These values are intentionally small
# so the post-processing does not expand the prediction to the whole RGI area.
MORPH_CLOSE_KERNEL_SIZE = 5
MORPH_CLOSE_ITERATIONS = 1
MORPH_OPEN_KERNEL_SIZE = 3
MORPH_OPEN_ITERATIONS = 1

INFERENCE_BATCH_SIZE = 8

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ==========================================================
# CPU CONFIGURATION
# ==========================================================

if DEVICE.type == "cpu":

    cpu_count = os.cpu_count() or 4

    torch.set_num_threads(
        min(
            4,
            cpu_count,
        )
    )


# ==========================================================
# LOAD MODEL ONCE
# ==========================================================

print()
print("==========================================")
print(" GLACIERAI - U-NET V3")
print("==========================================")
print()

print(
    "Device:",
    DEVICE,
)

print(
    "Loading model..."
)

model = UNet().to(
    DEVICE
)

checkpoint = torch.load(
    MODEL_PATH,
    map_location=DEVICE,
)

model.load_state_dict(
    checkpoint[
        "model_state_dict"
    ]
)

model.eval()

print(
    "Model loaded successfully!"
)

print(
    "Checkpoint epoch:",
    checkpoint.get(
        "epoch",
        30,
    ),
)

print()


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_band(
    band: np.ndarray,
) -> np.ndarray:
    """
    Convert Sentinel-2 L2A scaled reflectance
    to the 0-255 uint8 representation used
    by the training pipeline.
    """

    band = band.astype(
        np.float32
    )

    # Sentinel-2 L2A reflectance
    # is commonly stored with scale factor 10000.
    band = band / 10000.0

    band = np.clip(
        band,
        0.0,
        1.0,
    )

    return (
        band * 255.0
    ).astype(
        np.uint8
    )


# ==========================================================
# CREATE RGI POLYGON MASK
# ==========================================================

def create_rgi_mask(
    geometry,
    raster_shape,
    raster_transform,
    raster_crs,
):
    """
    Convert the RGI glacier polygon from EPSG:4326
    into the Sentinel-2 GeoTIFF CRS and rasterize it
    onto the exact image grid.
    """

    if geometry is None:

        return np.ones(
            raster_shape,
            dtype=np.uint8,
        )

    if raster_crs is None:

        raise ValueError(
            "GeoTIFF CRS is missing. "
            "Cannot align RGI geometry."
        )

    print()
    print(
        "Creating RGI glacier polygon mask..."
    )

    # ------------------------------------------------------
    # RGI geometry is stored in EPSG:4326
    # ------------------------------------------------------

    transformed_geometry = transform_geom(
        "EPSG:4326",
        raster_crs,
        geometry,
        precision=6,
    )

    # ------------------------------------------------------
    # Rasterize polygon onto Sentinel image grid
    # ------------------------------------------------------

    rgi_mask = rasterize(
        [
            (
                transformed_geometry,
                1,
            )
        ],
        out_shape=raster_shape,
        transform=raster_transform,
        fill=0,
        dtype=np.uint8,
        all_touched=False,
    )

    rgi_pixels = int(
        rgi_mask.sum()
    )

    # Very small RGI polygons can fall between Sentinel-2 pixel centres.
    # Retry only in that edge case so ordinary polygons remain conservative.
    if rgi_pixels == 0:
        print(
            "RGI polygon missed the pixel grid; retrying with "
            "all_touched=True for a small-glacier-safe rasterization."
        )

        rgi_mask = rasterize(
            [
                (
                    transformed_geometry,
                    1,
                )
            ],
            out_shape=raster_shape,
            transform=raster_transform,
            fill=0,
            dtype=np.uint8,
            all_touched=True,
        )

        rgi_pixels = int(
            rgi_mask.sum()
        )

    print(
        "RGI polygon pixels:",
        rgi_pixels,
    )

    if rgi_pixels == 0:

        raise ValueError(
            "RGI polygon does not overlap "
            "the downloaded Sentinel-2 image."
        )

    return rgi_mask


# ==========================================================
# MAIN PREDICTION FUNCTION
# ==========================================================

def predict_geotiff(
    image_path,
    output_stem: str = "glacier",
    rgi_geometry=None,
):

    image_path = Path(
        image_path
    )

    if not image_path.exists():

        raise FileNotFoundError(
            f"GeoTIFF not found: "
            f"{image_path}"
        )

    # ======================================================
    # READ GEOTIFF
    # ======================================================

    print(
        "Reading GeoTIFF..."
    )

    with rasterio.open(
        image_path
    ) as src:

        width = src.width
        height = src.height

        red = src.read(
            1
        ).astype(
            np.float32
        )

        green = src.read(
            2
        ).astype(
            np.float32
        )

        blue = src.read(
            3
        ).astype(
            np.float32
        )

        source_profile = (
            src.profile.copy()
        )

        transform = src.transform
        crs = src.crs

        pixel_width = abs(
            transform.a
        )

        pixel_height = abs(
            transform.e
        )

    print()
    print(
        "Image size:",
        width,
        "x",
        height,
    )

    print(
        "CRS:",
        crs,
    )

    print(
        "Resolution:",
        pixel_width,
        "x",
        pixel_height,
        "m",
    )

    # ======================================================
    # RGI POLYGON MASK
    # ======================================================

    rgi_mask = create_rgi_mask(
        geometry=rgi_geometry,
        raster_shape=(
            height,
            width,
        ),
        raster_transform=transform,
        raster_crs=crs,
    )

    # ======================================================
    # TRAINING-COMPATIBLE NORMALIZATION
    # ======================================================

    print()
    print(
        "Applying training-compatible normalization..."
    )

    red = normalize_band(
        red
    )

    green = normalize_band(
        green
    )

    blue = normalize_band(
        blue
    )

    rgb = np.dstack(
        (
            red,
            green,
            blue,
        )
    )

    # ======================================================
    # PADDING
    # ======================================================

    if height < PATCH_SIZE:

        pad_height = (
            PATCH_SIZE
            - height
        )

    else:

        pad_height = (
            PATCH_SIZE
            - (
                (
                    height
                    - PATCH_SIZE
                )
                % STRIDE
            )
        ) % STRIDE

    if width < PATCH_SIZE:

        pad_width = (
            PATCH_SIZE
            - width
        )

    else:

        pad_width = (
            PATCH_SIZE
            - (
                (
                    width
                    - PATCH_SIZE
                )
                % STRIDE
            )
        ) % STRIDE

    if (
        pad_height > 0
        or pad_width > 0
    ):

        rgb_padded = cv2.copyMakeBorder(
            rgb,
            0,
            pad_height,
            0,
            pad_width,
            cv2.BORDER_REFLECT,
        )

    else:

        rgb_padded = rgb

    padded_height = (
        rgb_padded.shape[0]
    )

    padded_width = (
        rgb_padded.shape[1]
    )

    # ======================================================
    # PATCH POSITIONS
    # ======================================================

    y_positions = list(
        range(
            0,
            padded_height
            - PATCH_SIZE
            + 1,
            STRIDE,
        )
    )

    x_positions = list(
        range(
            0,
            padded_width
            - PATCH_SIZE
            + 1,
            STRIDE,
        )
    )

    total_patches = (
        len(y_positions)
        * len(x_positions)
    )

    print()
    print(
        "Total patches:",
        total_patches,
    )

    print(
        "Inference batch size:",
        INFERENCE_BATCH_SIZE,
    )

    print()
    print(
        "Running U-Net V3..."
    )

    # ======================================================
    # ACCUMULATORS
    # ======================================================

    probability_sum = np.zeros(
        (
            padded_height,
            padded_width,
        ),
        dtype=np.float32,
    )

    prediction_count = np.zeros(
        (
            padded_height,
            padded_width,
        ),
        dtype=np.float32,
    )

    # Give the centre of each patch slightly more influence than its edges.
    # This reduces seam/border artefacts when overlapping patches are merged.
    gaussian_1d = cv2.getGaussianKernel(
        PATCH_SIZE,
        PATCH_SIZE / 6.0,
    )

    blend_weight = (
        gaussian_1d @ gaussian_1d.T
    ).astype(
        np.float32
    )

    blend_weight /= float(
        blend_weight.max()
    )

    # ======================================================
    # CREATE PATCH LIST
    # ======================================================

    patch_locations = []
    patches = []

    for y in y_positions:

        for x in x_positions:

            patch = rgb_padded[
                y:y + PATCH_SIZE,
                x:x + PATCH_SIZE,
            ]

            patches.append(
                patch
            )

            patch_locations.append(
                (
                    y,
                    x,
                )
            )

    # ======================================================
    # BATCH INFERENCE
    # ======================================================

    processed = 0

    with torch.no_grad():

        for start in range(
            0,
            len(patches),
            INFERENCE_BATCH_SIZE,
        ):

            batch_patches = patches[
                start:
                start
                + INFERENCE_BATCH_SIZE
            ]

            batch_locations = (
                patch_locations[
                    start:
                    start
                    + INFERENCE_BATCH_SIZE
                ]
            )

            batch_array = np.stack(
                batch_patches,
                axis=0,
            )

            tensor = (
                torch.from_numpy(
                    batch_array.astype(
                        np.float32
                    )
                    / 255.0
                )
                .permute(
                    0,
                    3,
                    1,
                    2,
                )
                .to(DEVICE)
            )

            output = model(
                tensor
            )

            probabilities = (
                torch.sigmoid(
                    output
                )
                .squeeze(1)
                .cpu()
                .numpy()
            )

            for index, (
                y,
                x,
            ) in enumerate(
                batch_locations
            ):

                probability_sum[
                    y:y + PATCH_SIZE,
                    x:x + PATCH_SIZE,
                ] += (
                    probabilities[index]
                    * blend_weight
                )

                prediction_count[
                    y:y + PATCH_SIZE,
                    x:x + PATCH_SIZE,
                ] += blend_weight

            processed += len(
                batch_locations
            )

            print(
                f"Processed "
                f"{processed}/"
                f"{total_patches} patches"
            )

    # ======================================================
    # AVERAGE OVERLAPPING PATCHES
    # ======================================================

    prediction_count[
        prediction_count == 0
    ] = 1

    full_probability = (
        probability_sum
        / prediction_count
    )

    # ======================================================
    # GLOBAL PROBABILITY STATISTICS
    # ======================================================

    print()
    print(
        "Probability statistics:"
    )

    print(
        "Min:",
        float(
            full_probability.min()
        )
    )

    print(
        "Max:",
        float(
            full_probability.max()
        )
    )

    print(
        "Mean:",
        float(
            full_probability.mean()
        )
    )

    print(
        "Pixels >= 0.1:",
        int(
            (
                full_probability
                >= 0.1
            ).sum()
        )
    )

    print(
        "Pixels >= 0.2:",
        int(
            (
                full_probability
                >= 0.2
            ).sum()
        )
    )

    print(
        "Pixels >= 0.3:",
        int(
            (
                full_probability
                >= 0.3
            ).sum()
        )
    )

    print(
        "Pixels >= 0.4:",
        int(
            (
                full_probability
                >= 0.4
            ).sum()
        )
    )

    print(
        "Pixels >= 0.5:",
        int(
            (
                full_probability
                >= 0.5
            ).sum()
        )
    )

    # ======================================================
    # REMOVE PADDING
    # ======================================================

    full_probability = (
        full_probability[
            :height,
            :width,
        ]
    )

    np.save(
        OUTPUT_DIR
        / f"{output_stem}_probability.npy",
        full_probability,
    )

    # ======================================================
    # PROBABILITY INSIDE RGI POLYGON
    # ======================================================

    print()
    print(
        "Probability statistics INSIDE RGI polygon:"
    )

    rgi_probabilities = (
        full_probability[
            rgi_mask == 1
        ]
    )

    if rgi_probabilities.size == 0:

        raise ValueError(
            "No pixels found inside "
            "the RGI polygon."
        )

    print(
        "RGI probability min:",
        float(
            rgi_probabilities.min()
        )
    )

    print(
        "RGI probability max:",
        float(
            rgi_probabilities.max()
        )
    )

    print(
        "RGI probability mean:",
        float(
            rgi_probabilities.mean()
        )
    )

    print(
        "RGI pixels >= 0.1:",
        int(
            (
                rgi_probabilities
                >= 0.1
            ).sum()
        )
    )

    print(
        "RGI pixels >= 0.2:",
        int(
            (
                rgi_probabilities
                >= 0.2
            ).sum()
        )
    )

    print(
        "RGI pixels >= 0.3:",
        int(
            (
                rgi_probabilities
                >= 0.3
            ).sum()
        )
    )

    print(
        "RGI pixels >= 0.4:",
        int(
            (
                rgi_probabilities
                >= 0.4
            ).sum()
        )
    )

    print(
        "RGI pixels >= 0.5:",
        int(
            (
                rgi_probabilities
                >= 0.5
            ).sum()
        )
    )
        # ======================================================
    # XAI CONFIDENCE ANALYSIS
    # ======================================================

    # These counters are populated by the morphology stage below.
    # Initialize them here because xai_statistics is created before
    # the final mask is built.
    morphology_added_pixels = 0
    morphology_removed_pixels = 0

    # Probability ranges inside the RGI glacier boundary
    low_confidence_pixels = int(
        ((rgi_probabilities >= 0.0) &
         (rgi_probabilities < 0.20)).sum()
    )

    uncertain_pixels = int(
        ((rgi_probabilities >= 0.20) &
         (rgi_probabilities < 0.50)).sum()
    )

    moderate_confidence_pixels = int(
        ((rgi_probabilities >= 0.50) &
         (rgi_probabilities < 0.80)).sum()
    )

    high_confidence_pixels = int(
        (rgi_probabilities >= 0.80).sum()
    )

    total_rgi_probability_pixels = int(
        rgi_probabilities.size
    )

    xai_confidence = {
        "low": round(
            low_confidence_pixels /
            total_rgi_probability_pixels * 100,
            2
        ),

        "uncertain": round(
            uncertain_pixels /
            total_rgi_probability_pixels * 100,
            2
        ),

        "moderate": round(
            moderate_confidence_pixels /
            total_rgi_probability_pixels * 100,
            2
        ),

        "high": round(
            high_confidence_pixels /
            total_rgi_probability_pixels * 100,
            2
        ),
    }

    xai_statistics = {
        "mean_probability": round(
            float(rgi_probabilities.mean()),
            4
        ),

        "minimum_probability": round(
            float(rgi_probabilities.min()),
            4
        ),

        "maximum_probability": round(
            float(rgi_probabilities.max()),
            4
        ),

        "threshold": THRESHOLD,

        "core_threshold": CORE_THRESHOLD,

        "confidence_distribution_percent": xai_confidence,

        "segmentation_postprocessing": {
            "method": "confidence_aware_morphology_and_connected_components",
            "min_component_pixels": MIN_COMPONENT_PIXELS,
            "min_component_mean_probability": MIN_COMPONENT_MEAN_PROBABILITY,
            "overlap_blending": "gaussian_center_weighted",
            "morphological_refinement": {
                "method": "conservative_close_then_open",
                "close_kernel_size": MORPH_CLOSE_KERNEL_SIZE,
                "close_iterations": MORPH_CLOSE_ITERATIONS,
                "open_kernel_size": MORPH_OPEN_KERNEL_SIZE,
                "open_iterations": MORPH_OPEN_ITERATIONS,
                "pixels_added": morphology_added_pixels,
                "pixels_removed": morphology_removed_pixels,
            },
        },

        "pixel_counts": {
            "low": low_confidence_pixels,
            "uncertain": uncertain_pixels,
            "moderate": moderate_confidence_pixels,
            "high": high_confidence_pixels,
            "total": total_rgi_probability_pixels,
        },

        "explanation":
            "The confidence map represents the U-Net probability "
            "for each pixel being classified as glacier. "
            "Higher probability indicates stronger model confidence."
    }
    # ======================================================
    # CONFIDENCE-AWARE FINAL U-NET MASK
    # ======================================================

    print()
    print(
        "Building confidence-aware glacier mask..."
    )

    # Start with the model's existing threshold.
    candidate_mask = (
        full_probability >= THRESHOLD
    ).astype(
        np.uint8
    )

    # High-confidence pixels act as seeds. This remains separate from the
    # morphology so the refinement never changes the model's confidence map.
    core_mask = (
        full_probability >= CORE_THRESHOLD
    ).astype(
        np.uint8
    )

    # Restrict both masks to the known RGI glacier footprint.
    candidate_mask[
        rgi_mask == 0
    ] = 0

    core_mask[
        rgi_mask == 0
    ] = 0

    # ======================================================
    # CONSERVATIVE MORPHOLOGICAL REFINEMENT
    # ======================================================
    #
    # The probability diagnostic showed that the >= 0.20 prediction is
    # fragmented into many components. Before component filtering, use a
    # very small closing operation to reconnect only nearby gaps and a small
    # opening operation to remove isolated speckle noise.
    #
    # This does NOT lower the probability threshold and does NOT fill the RGI
    # polygon. The RGI polygon remains only a spatial constraint.
    # ======================================================

    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (
            MORPH_CLOSE_KERNEL_SIZE,
            MORPH_CLOSE_KERNEL_SIZE,
        ),
    )

    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (
            MORPH_OPEN_KERNEL_SIZE,
            MORPH_OPEN_KERNEL_SIZE,
        ),
    )

    candidate_before_morphology = candidate_mask.copy()

    candidate_mask = cv2.morphologyEx(
        candidate_mask,
        cv2.MORPH_CLOSE,
        close_kernel,
        iterations=MORPH_CLOSE_ITERATIONS,
    )

    candidate_mask = cv2.morphologyEx(
        candidate_mask,
        cv2.MORPH_OPEN,
        open_kernel,
        iterations=MORPH_OPEN_ITERATIONS,
    )

    # Never allow morphology to leave the RGI footprint.
    candidate_mask[
        rgi_mask == 0
    ] = 0

    morphology_added_pixels = int(
        (
            (candidate_mask == 1)
            & (candidate_before_morphology == 0)
        ).sum()
    )

    morphology_removed_pixels = int(
        (
            (candidate_mask == 0)
            & (candidate_before_morphology == 1)
        ).sum()
    )

    print()
    print(
        "Morphological refinement:"
    )
    print(
        "  Close kernel:",
        MORPH_CLOSE_KERNEL_SIZE,
        "x",
        MORPH_CLOSE_KERNEL_SIZE,
    )
    print(
        "  Open kernel:",
        MORPH_OPEN_KERNEL_SIZE,
        "x",
        MORPH_OPEN_KERNEL_SIZE,
    )
    print(
        "  Pixels added by morphology:",
        morphology_added_pixels,
    )
    print(
        "  Pixels removed by morphology:",
        morphology_removed_pixels,
    )

    # Update the XAI metadata with the actual morphology diagnostics.
    xai_statistics["segmentation_postprocessing"][
        "morphological_refinement"
    ]["pixels_added"] = morphology_added_pixels

    xai_statistics["segmentation_postprocessing"][
        "morphological_refinement"
    ]["pixels_removed"] = morphology_removed_pixels

    # Connected-component analysis lets us keep genuinely small glacier
    # pieces while removing isolated low-probability noise.
    component_count, component_labels, component_stats, _ = cv2.connectedComponentsWithStats(
        candidate_mask,
        connectivity=8,
    )

    mask = np.zeros_like(
        candidate_mask,
        dtype=np.uint8,
    )

    kept_components = 0
    removed_components = 0

    for component_id in range(
        1,
        component_count,
    ):

        component_area = int(
            component_stats[
                component_id,
                cv2.CC_STAT_AREA,
            ]
        )

        if component_area < MIN_COMPONENT_PIXELS:
            # Preserve tiny components only when they contain a
            # high-confidence model pixel. This protects genuinely tiny
            # glaciers without accepting isolated weak noise.
            component_core = (
                (
                    component_labels
                    == component_id
                )
                & (
                    core_mask
                    == 1
                )
            )

            if not np.any(
                component_core
            ):
                removed_components += 1
                continue

        component_pixels = (
            component_labels
            == component_id
        )

        component_probabilities = (
            full_probability[
                component_pixels
            ]
        )

        mean_probability = float(
            component_probabilities.mean()
        ) if component_probabilities.size else 0.0

        contains_core = bool(
            np.any(
                core_mask[
                    component_pixels
                ]
                == 1
            )
        )

        # Keep a component when:
        #   1. it contains a strong model seed, OR
        #   2. it is large enough and has a reasonably strong mean
        #      probability.
        keep_component = (
            contains_core
            or (
                component_area
                >= MIN_COMPONENT_PIXELS
                and mean_probability
                >= MIN_COMPONENT_MEAN_PROBABILITY
            )
        )

        if keep_component:
            mask[
                component_pixels
            ] = 1
            kept_components += 1
        else:
            removed_components += 1

    # ======================================================
    # APPLY RGI POLYGON MASK
    # ======================================================

    print()
    print(
        "Applying RGI polygon to U-Net prediction..."
    )

    mask[
        rgi_mask == 0
    ] = 0

    print(
        "Candidate pixels:",
        int(candidate_mask.sum()),
    )

    print(
        "Core pixels:",
        int(core_mask.sum()),
    )

    print(
        "Kept components:",
        kept_components,
    )

    print(
        "Removed components:",
        removed_components,
    )

    print(
        "Final glacier pixels:",
        int(mask.sum()),
    )

    # ======================================================
    # AREA
    # ======================================================

    glacier_pixels = int(
        mask.sum()
    )

    total_pixels = int(
        rgi_mask.sum()
    )

    pixel_area_m2 = (
        pixel_width
        * pixel_height
    )

    glacier_area_m2 = (
        glacier_pixels
        * pixel_area_m2
    )

    glacier_area_km2 = (
        glacier_area_m2
        / 1_000_000
    )

    coverage_percent = (
        glacier_pixels
        / total_pixels
    ) * 100

    # ======================================================
    # OUTPUT FILENAMES
    # ======================================================

    mask_tif_path = (
        OUTPUT_DIR
        / f"{output_stem}_glacier_mask.tif"
    )

    mask_png_path = (
        OUTPUT_DIR
        / f"{output_stem}_full_mask.png"
    )

    overlay_path = (
        OUTPUT_DIR
        / f"{output_stem}_full_overlay.png"
    )

    rgi_mask_png_path = (
        OUTPUT_DIR
        / f"{output_stem}_rgi_mask.png"
    )

    rgb_path = (
        OUTPUT_DIR
        / f"{output_stem}_full_rgb.png"
    )

    probability_heatmap_path = (
        OUTPUT_DIR
        / f"{output_stem}_probability_heatmap.png"
    )

    probability_overlay_path = (
        OUTPUT_DIR
        / f"{output_stem}_probability_overlay.png"
    )

    # ======================================================
    # SAVE GEOTIFF MASK
    # ======================================================

    mask_profile = (
        source_profile.copy()
    )

    mask_profile.update(
        {
            "count": 1,
            "dtype": "uint8",
            "compress": "lzw",
        }
    )

    with rasterio.open(
        mask_tif_path,
        "w",
        **mask_profile,
    ) as dst:

        dst.write(
            mask,
            1,
        )

    # ======================================================
    # SAVE RGI POLYGON MASK PNG
    # ======================================================

    cv2.imwrite(
        str(rgi_mask_png_path),
        rgi_mask * 255,
    )

    # ======================================================
    # SAVE BINARY PNG MASK
    # ======================================================

    cv2.imwrite(
        str(mask_png_path),
        mask * 255,
    )

    # ======================================================
    # CREATE VISUALIZATION OUTPUTS
    # ======================================================

    print()
    print(
        "Creating visualization outputs..."
    )

    # ------------------------------------------------------
    # 1. ORIGINAL SENTINEL RGB
    # ------------------------------------------------------

    cv2.imwrite(
        str(rgb_path),
        cv2.cvtColor(
            rgb,
            cv2.COLOR_RGB2BGR,
        ),
    )

    # ------------------------------------------------------
    # 2. U-NET PROBABILITY HEATMAP
    # ------------------------------------------------------

    probability_uint8 = (
        np.clip(
            full_probability,
            0.0,
            1.0,
        )
        * 255
    ).astype(
        np.uint8
    )

    probability_heatmap = cv2.applyColorMap(
        probability_uint8,
        cv2.COLORMAP_JET,
    )

    outside_rgi = (
        rgi_mask == 0
    )

    probability_heatmap[
        outside_rgi
    ] = [
        0,
        0,
        0,
    ]

    cv2.imwrite(
        str(probability_heatmap_path),
        probability_heatmap,
    )

    # ------------------------------------------------------
    # 3. PROBABILITY OVERLAY
    # ------------------------------------------------------

    probability_heatmap_rgb = cv2.cvtColor(
        probability_heatmap,
        cv2.COLOR_BGR2RGB,
    )

    probability_overlay = cv2.addWeighted(
        rgb,
        0.60,
        probability_heatmap_rgb,
        0.40,
        0,
    )

    probability_overlay[
        outside_rgi
    ] = rgb[
        outside_rgi
    ]

    cv2.imwrite(
        str(probability_overlay_path),
        cv2.cvtColor(
            probability_overlay,
            cv2.COLOR_RGB2BGR,
        ),
    )

    # ------------------------------------------------------
    # 4. BINARY MASK OVERLAY
    # ------------------------------------------------------

    overlay = rgb.copy()

    overlay[
        mask == 1
    ] = [
        255,
        0,
        0,
    ]

    overlay = cv2.addWeighted(
        rgb,
        0.65,
        overlay,
        0.35,
        0,
    )

    cv2.imwrite(
        str(overlay_path),
        cv2.cvtColor(
            overlay,
            cv2.COLOR_RGB2BGR,
        ),
    )

    print(
        "RGB image:",
        rgb_path,
    )

    print(
        "Probability heatmap:",
        probability_heatmap_path,
    )

    print(
        "Probability overlay:",
        probability_overlay_path,
    )

    print(
        "Binary mask overlay:",
        overlay_path,
    )

    # ======================================================
    # RESULTS
    # ======================================================

    print()
    print(
        "=========================================="
    )

    print(
        " GLACIER ANALYSIS COMPLETE"
    )

    print(
        "=========================================="
    )

    print()

    print(
        "Model:",
        "U-Net V3",
    )

    print(
        "RGI polygon applied:",
        rgi_geometry is not None,
    )

    print(
        "RGI valid pixels:",
        total_pixels,
    )

    print(
        "Glacier pixels:",
        glacier_pixels,
    )

    print(
        "Glacier coverage:",
        round(
            coverage_percent,
            2,
        ),
        "%",
    )

    print(
        "Glacier area:",
        round(
            glacier_area_m2,
            2,
        ),
        "mÂ²",
    )

    print(
        "Glacier area:",
        round(
            glacier_area_km2,
            6,
        ),
        "kmÂ²",
    )

    print()

    # ======================================================
    # RETURN RESULTS
    # ======================================================

    return {

        "glacier_pixels":
            glacier_pixels,

        "total_pixels":
            total_pixels,

        "coverage_percent":
            round(
                coverage_percent,
                2,
            ),

        "area_m2":
            round(
                glacier_area_m2,
                2,
            ),

        "area_km2":
            round(
                glacier_area_km2,
                6,
            ),

        "mask_path":
            str(mask_tif_path),

        "mask_png_path":
            str(mask_png_path),

        "overlay_path":
            str(overlay_path),

        "rgb_path":
            str(rgb_path),

        "probability_heatmap_path":
            str(probability_heatmap_path),

        "probability_overlay_path":
            str(probability_overlay_path),

        "rgi_mask_png_path":
            str(rgi_mask_png_path),

        "crs":
            str(crs),

        "rgi_polygon_applied":
            rgi_geometry is not None,
        "xai": xai_statistics,
    }


# ==========================================================
# DIRECT TEST â€” KHUMBU
# ==========================================================

if __name__ == "__main__":

    from backend.app.services.rgi_service import (
        find_nearest_glacier
    )

    # ------------------------------------------------------
    # Freshly downloaded Khumbu Sentinel image
    # ------------------------------------------------------

    test_image = (
        PROJECT_ROOT
        / "datasets"
        / "live"
        / "khumbu_fixed.tif"
    )

    print()
    print(
        "Looking up nearest RGI glacier....."
    )

    glacier = find_nearest_glacier(
        27.976805,
        86.904919,
    )

    if glacier is None:

        print(
            "ERROR: No RGI glacier found near "
            "the Sentinel image."
        )

        raise SystemExit(1)

    print(
        f"RGI ID      : "
        f"{glacier['rgi_id']}"
    )

    print(
        f"Glacier     : "
        f"{glacier['name']}"
    )

    print(
        f"RGI Area    : "
        f"{glacier['area_km2']} kmÂ²"
    )

    rgi_geometry = glacier.get(
        "geometry"
    )

    if rgi_geometry is None:

        print(
            "ERROR: RGI geometry was not returned."
        )

        raise SystemExit(1)

    print(
        "RGI geometry loaded successfully."
    )

    result = predict_geotiff(
        image_path=test_image,
        output_stem="khumbu",
        rgi_geometry=rgi_geometry,
    )

    print()
    print(
        "Prediction finished."
    )