import torch
import rasterio
import numpy as np

from backend.models.unet import UNet


IMAGE_PATH = "datasets/live/gangotri_latest.tif"
V2_PATH = "checkpoints/best_unet_v2.pth"
V3_PATH = "checkpoints/best_unet_v3.pth"


def load_model(path):
    model = UNet()

    checkpoint = torch.load(
        path,
        map_location="cpu"
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model.eval()

    return model


# -----------------------------
# Load first 256x256 image patch
# -----------------------------

with rasterio.open(IMAGE_PATH) as src:

    red = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    blue = src.read(3).astype(np.float32)

patch = np.dstack(
    (
        red[:256, :256],
        green[:256, :256],
        blue[:256, :256],
    )
)

# Same normalization used by predict_geotiff.py
patch = patch / 10000.0
patch = np.clip(patch, 0.0, 1.0)

tensor = torch.from_numpy(
    patch.astype(np.float32)
).permute(
    2, 0, 1
).unsqueeze(0)


# -----------------------------
# Load V2 and V3
# -----------------------------

v2 = load_model(V2_PATH)
v3 = load_model(V3_PATH)


# -----------------------------
# Predict
# -----------------------------

with torch.no_grad():

    v2_output = torch.sigmoid(
        v2(tensor)
    )

    v3_output = torch.sigmoid(
        v3(tensor)
    )


v2_output = v2_output.numpy()
v3_output = v3_output.numpy()


# -----------------------------
# Compare
# -----------------------------

print()
print("===================================")
print(" V2 vs V3 DIRECT COMPARISON")
print("===================================")

print()
print("V2:")
print("Min:", v2_output.min())
print("Max:", v2_output.max())
print("Mean:", v2_output.mean())

print()
print("V3:")
print("Min:", v3_output.min())
print("Max:", v3_output.max())
print("Mean:", v3_output.mean())

difference = np.abs(
    v2_output - v3_output
)

print()
print("Difference:")
print("Max difference:", difference.max())
print("Mean difference:", difference.mean())
print(
    "Identical:",
    np.array_equal(v2_output, v3_output)
)