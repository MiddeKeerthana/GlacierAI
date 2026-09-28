"""
GlacierAI - Historical Visualization

Displays the four historical Sentinel-2 images side-by-side
for visual validation before interpreting area changes.
"""

from pathlib import Path

import matplotlib.pyplot as plt
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


def normalize_image(image):
    """Normalize satellite bands for visualization."""

    image = image.astype(np.float32)

    output = np.zeros_like(image, dtype=np.float32)

    for band in range(image.shape[2]):

        channel = image[:, :, band]

        low = np.percentile(channel, 2)
        high = np.percentile(channel, 98)

        if high > low:
            channel = np.clip(
                (channel - low) / (high - low),
                0,
                1
            )
        else:
            channel = np.zeros_like(channel)

        output[:, :, band] = channel

    return output


def main():

    print("=" * 60)
    print(" GLACIERAI - HISTORICAL VISUALIZATION")
    print("=" * 60)

    images = []

    for date in DATES:

        file_path = (
            SATELLITE_DIR
            / f"gangotri_{date}.tif"
        )

        if not file_path.exists():
            print(f"\nERROR: File not found:")
            print(file_path)
            continue

        print(f"\nLoading: {file_path.name}")

        with rasterio.open(file_path) as src:

            image = src.read()

            print(f"  Shape: {image.shape}")
            print(f"  CRS: {src.crs}")
            print(
                f"  Resolution: "
                f"{src.res[0]:.3f} x {src.res[1]:.3f} m"
            )

        # Convert CHW → HWC
        image = np.transpose(image, (1, 2, 0))

        # Make sure we have 3 display bands
        if image.shape[2] >= 3:
            image = image[:, :, :3]

        image = normalize_image(image)

        images.append(
            {
                "date": date,
                "image": image
            }
        )

    if not images:
        print("\nNo images found.")
        return

    # --------------------------------------------------------
    # CREATE 2 x 2 FIGURE
    # --------------------------------------------------------

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(16, 12)
    )

    axes = axes.flatten()

    for ax in axes:
        ax.axis("off")

    for ax, item in zip(axes, images):

        ax.imshow(item["image"])

        ax.set_title(
            f"Sentinel-2 | {item['date']}",
            fontsize=14,
            fontweight="bold"
        )

        ax.axis("off")

    plt.suptitle(
        "GlacierAI - Historical Sentinel-2 Observations",
        fontsize=18,
        fontweight="bold"
    )

    plt.tight_layout()

    output_file = (
        PROJECT_ROOT
        / "datasets"
        / "historical"
        / "historical_satellite_comparison.png"
    )

    plt.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight"
    )

    print("\n" + "=" * 60)
    print(" VISUALIZATION COMPLETE")
    print("=" * 60)

    print(f"\nSaved comparison image:")
    print(output_file)

    plt.show()


if __name__ == "__main__":
    main()