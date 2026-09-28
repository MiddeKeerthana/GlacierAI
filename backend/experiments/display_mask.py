import rasterio
import matplotlib.pyplot as plt
import numpy as np

mask_path = "datasets/masks/gangotri_mask.tif"

with rasterio.open(mask_path) as src:
    mask = src.read(1)

print("Shape:", mask.shape)
print("Unique values:", np.unique(mask))
print("Glacier pixels:", np.count_nonzero(mask))

plt.figure(figsize=(10,10))
plt.imshow(mask, cmap="gray", vmin=0, vmax=1)
plt.title("Glacier Mask")
plt.axis("off")
plt.show()