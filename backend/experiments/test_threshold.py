from app.config import SENTINEL_DATA

from app.services.sentinel_reader import (
    find_safe_folder,
    read_band,
    get_band_path,
)

from app.preprocessing.resampling import read_band_resampled
from app.preprocessing.indices import compute_ndsi
from app.preprocessing.threshold import ndsi_threshold

import matplotlib.pyplot as plt

# Find SAFE folder
safe_folder = find_safe_folder(
    SENTINEL_DATA,
    "T44SKA"
)

print("Using:", safe_folder.name)

# Read Green band
green = read_band(
    str(safe_folder),
    "B03"
)

# Read SWIR
b11_path = get_band_path(
    str(safe_folder),
    "B11"
)

swir = read_band_resampled(
    b11_path,
    green.shape
)

# Compute NDSI
ndsi = compute_ndsi(
    green,
    swir
)

# Binary mask
mask = ndsi_threshold(
    ndsi,
    threshold=0.4
)

# Preview
preview = mask[::10, ::10]

plt.figure(figsize=(8,8))

plt.imshow(
    preview,
    cmap="gray"
)

plt.title("Binary Snow / Ice Mask")

plt.axis("off")

plt.show()