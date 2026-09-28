from app.config import SENTINEL_DATA

from app.services.sentinel_reader import (
    find_safe_folder,
    read_band,
)

import numpy as np
import matplotlib.pyplot as plt

safe_folder = find_safe_folder(SENTINEL_DATA, "T44SKA")

print("Using:", safe_folder)

red = read_band(str(safe_folder), "B04")
green = read_band(str(safe_folder), "B03")
blue = read_band(str(safe_folder), "B02")

rgb = np.dstack((red, green, blue)).astype(np.float32)

rgb /= np.percentile(rgb, 99)

rgb = np.clip(rgb, 0, 1)

rgb = rgb[::10, ::10]

plt.figure(figsize=(8,8))
plt.imshow(rgb)
plt.title("Sentinel-2 RGB")
plt.axis("off")
plt.show()