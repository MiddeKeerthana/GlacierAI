"""
GlacierAI - Historical Satellite Data Validation

Checks:
- TIFF dimensions
- CRS
- resolution
- NoData value
- valid pixel percentage
- zero pixel percentage
- min/max/mean values
"""

from pathlib import Path

import numpy as np
import rasterio


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SATELLITE_DIR = (
    PROJECT_ROOT
    / "datasets"
    / "historical"
    / "satellite"
)

DATES = [
    "2023-09-26",
    "2024-09-30",
    "2025-09-22",
    "2026-09-19",
]


def main():

    print("=" * 70)
    print(" GLACIERAI - HISTORICAL SATELLITE DATA VALIDATION")
    print("=" * 70)

    for date in DATES:

        file_path = (
            SATELLITE_DIR
            / f"gangotri_{date}.tif"
        )

        print("\n" + "=" * 70)
        print(f" DATE: {date}")
        print("=" * 70)

        if not file_path.exists():
            print("ERROR: File not found")
            print(file_path)
            continue

        with rasterio.open(file_path) as src:

            print(f"\nFile: {file_path.name}")
            print(f"Width: {src.width}")
            print(f"Height: {src.height}")
            print(f"Bands: {src.count}")
            print(f"CRS: {src.crs}")
            print(f"Resolution: {src.res}")
            print(f"NoData: {src.nodata}")
            print(f"Dtype: {src.dtypes}")

            data = src.read().astype(np.float32)

        # ----------------------------------------------------
        # BASIC STATISTICS
        # ----------------------------------------------------

        total_pixels = data.shape[1] * data.shape[2]

        # A pixel is considered valid if at least one band
        # contains a non-zero value.
        valid_mask = np.any(data != 0, axis=0)

        valid_pixels = int(valid_mask.sum())

        zero_pixels = total_pixels - valid_pixels

        valid_percentage = (
            valid_pixels / total_pixels
        ) * 100

        zero_percentage = (
            zero_pixels / total_pixels
        ) * 100

        print("\nPixel coverage:")
        print(f"Total pixels: {total_pixels:,}")
        print(f"Valid pixels: {valid_pixels:,}")
        print(f"Zero pixels: {zero_pixels:,}")

        print(
            f"Valid coverage: "
            f"{valid_percentage:.2f}%"
        )

        print(
            f"Zero coverage: "
            f"{zero_percentage:.2f}%"
        )

        # ----------------------------------------------------
        # BAND STATISTICS
        # ----------------------------------------------------

        print("\nBand statistics:")

        for band_index in range(data.shape[0]):

            band = data[band_index]

            valid_values = band[valid_mask]

            if valid_values.size == 0:
                print(
                    f"Band {band_index + 1}: "
                    "NO VALID DATA"
                )
                continue

            print(
                f"Band {band_index + 1}: "
                f"min={valid_values.min():.2f}, "
                f"max={valid_values.max():.2f}, "
                f"mean={valid_values.mean():.2f}"
            )

    print("\n" + "=" * 70)
    print(" VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()