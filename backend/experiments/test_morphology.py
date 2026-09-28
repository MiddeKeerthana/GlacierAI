from app.config import SENTINEL_DATA

from app.services.sentinel_reader import (
    find_safe_folder,
    read_band,
    get_band_path,
)

from app.preprocessing.resampling import read_band_resampled
from app.preprocessing.indices import compute_ndsi
from app.preprocessing.threshold import ndsi_threshold
from app.preprocessing.morphology import clean_mask

import matplotlib.pyplot as plt

safe_folder = find_safe_folder(
    SENTINEL_DATA,
    "T44SKA"
)

green = read_band(
    str(safe_folder),
    "B03"
)

b11 = get_band_path(
    str(safe_folder),
    "B11"
)

swir = read_band_resampled(
    b11,
    green.shape
)

ndsi = compute_ndsi(
    green,
    swir
)

mask = ndsi_threshold(
    ndsi,
    threshold=0.4
)

clean = clean_mask(mask)

# ---------------------------------------------------------
# Compare masks (Fix uint64 overflow)
# ---------------------------------------------------------

before = int(mask.sum())
after = int(clean.sum())

print("\n========== MORPHOLOGY REPORT ==========")
print(f"Pixels before cleaning : {before}")
print(f"Pixels after cleaning  : {after}")

if after >= before:
    print(f"Pixels added           : {after - before}")
else:
    print(f"Pixels removed         : {before - after}")

print("=======================================\n")

preview = clean[::10, ::10]

plt.figure(figsize=(8, 8))

plt.imshow(
    preview,
    cmap="gray"
)

plt.title("Cleaned Glacier Mask")
plt.axis("off")
plt.show()