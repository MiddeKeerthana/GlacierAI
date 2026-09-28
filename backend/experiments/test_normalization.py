from pathlib import Path
import matplotlib.pyplot as plt

from app.services.sentinel_reader import read_band
from app.preprocessing.normalization import normalize_band

# Select T44SKA tile
safe_root = Path(__file__).resolve().parent.parent / "datasets" / "raw" / "Sentinel2"

safe_folder = next(
    folder for folder in safe_root.rglob("*.SAFE")
    if "T44SKA" in folder.name
)

# Read Red band
red = read_band(str(safe_folder), "B04")

# Normalize
red_norm = normalize_band(red)

# Preview
preview = red_norm[::10, ::10]

plt.figure(figsize=(8,8))
plt.imshow(preview, cmap="gray")
plt.title("Normalized B04")
plt.axis("off")
plt.show()