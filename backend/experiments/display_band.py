from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from app.services.sentinel_reader import read_band_info

# Locate SAFE folder
safe_root = Path(__file__).resolve().parent.parent / "datasets" / "raw" / "Sentinel2"
safe_folder = list(safe_root.rglob("*.SAFE"))[0]

image, metadata = read_band_info(str(safe_folder), band="B04")

print(metadata)
print("Minimum:", image.min())
print("Maximum:", image.max())

# Normalize
image = image.astype(np.float32)
image = (image - image.min()) / (image.max() - image.min())

# Downsample for display (every 10th pixel)
preview = image[::10, ::10]

plt.figure(figsize=(8,8))
plt.imshow(preview, cmap="gray")
plt.title("Sentinel-2 B04 Preview")
plt.axis("off")
plt.show()