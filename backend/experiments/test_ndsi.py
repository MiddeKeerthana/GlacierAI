from app.config import SENTINEL_DATA

from app.services.sentinel_reader import (
    find_safe_folder,
    read_band,
    get_band_path,
)

from app.preprocessing.resampling import read_band_resampled
from app.preprocessing.indices import compute_ndsi

import matplotlib.pyplot as plt

safe_folder = find_safe_folder(SENTINEL_DATA, "T44SKA")

print("Using:", safe_folder)

green = read_band(str(safe_folder), "B03")

b11_path = get_band_path(str(safe_folder), "B11")

swir = read_band_resampled(
    b11_path,
    green.shape
)

ndsi = compute_ndsi(
    green,
    swir
)

preview = ndsi[::10, ::10]

plt.figure(figsize=(8,8))
plt.imshow(preview, cmap="Blues")
plt.colorbar()

plt.title("NDSI")

plt.axis("off")

plt.show()