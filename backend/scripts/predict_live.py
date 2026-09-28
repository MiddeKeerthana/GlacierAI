from pathlib import Path

import cv2
import numpy as np
import torch

from backend.models.unet import UNet


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

IMAGE_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "live"
    / "gangotri_latest.png"
)

MODEL_PATH = (
    PROJECT_ROOT
    / "checkpoints"
    / "best_unet_v2.pth"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "datasets"
    / "live"
    / "predictions"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# CONFIGURATION
# ==========================================================

INPUT_SIZE = 256
THRESHOLD = 0.5

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ==========================================================
# LOAD MODEL
# ==========================================================

print()
print("==========================================")
print(" GLACIERAI - LIVE U-NET V2 ANALYSIS")
print("==========================================")
print()

print("Device :", DEVICE)
print()

print("Loading U-Net V2...")

model = UNet().to(DEVICE)

checkpoint = torch.load(
    MODEL_PATH,
    map_location=DEVICE
)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()

print("Model loaded successfully!")
print()

if isinstance(checkpoint, dict):

    if "epoch" in checkpoint:
        print("Checkpoint epoch :", checkpoint["epoch"])

    if "val_loss" in checkpoint:
        print(
            "Validation loss  :",
            round(checkpoint["val_loss"], 4)
        )

    if "val_dice" in checkpoint:
        print(
            "Validation Dice  :",
            round(checkpoint["val_dice"], 4)
        )

    if "val_iou" in checkpoint:
        print(
            "Validation IoU   :",
            round(checkpoint["val_iou"], 4)
        )

print()


# ==========================================================
# CHECK IMAGE
# ==========================================================

if not IMAGE_PATH.exists():

    raise FileNotFoundError(
        f"Live satellite image not found:\n{IMAGE_PATH}"
    )

print("Input image:")
print(IMAGE_PATH)
print()


# ==========================================================
# READ IMAGE
# ==========================================================

image = cv2.imread(
    str(IMAGE_PATH),
    cv2.IMREAD_COLOR
)

if image is None:

    raise ValueError(
        "Could not read the Sentinel-2 image."
    )


image = cv2.cvtColor(
    image,
    cv2.COLOR_BGR2RGB
)

print(
    "Original image size:",
    image.shape[1],
    "x",
    image.shape[0]
)


# ==========================================================
# TRAINING-COMPATIBLE NORMALIZATION
# ==========================================================
#
# The training dataset used percentile normalization:
#
# 2nd percentile  -> 0
# 98th percentile -> 255
#
# We reproduce that here for live imagery.
# ==========================================================

normalized = np.zeros_like(
    image,
    dtype=np.uint8
)

for channel in range(3):

    band = image[:, :, channel].astype(
        np.float32
    )

    low = np.percentile(
        band,
        2
    )

    high = np.percentile(
        band,
        98
    )

    if high > low:

        band = (
            (band - low)
            / (high - low)
        )

    else:

        band = np.zeros_like(
            band,
            dtype=np.float32
        )

    band = np.clip(
        band,
        0,
        1
    )

    normalized[:, :, channel] = (
        band * 255
    ).astype(np.uint8)


# ==========================================================
# RESIZE FOR U-NET
# ==========================================================

resized = cv2.resize(
    normalized,
    (INPUT_SIZE, INPUT_SIZE),
    interpolation=cv2.INTER_LINEAR
)


# ==========================================================
# CONVERT TO TENSOR
# ==========================================================

tensor = (
    torch.from_numpy(
        resized.astype(np.float32) / 255.0
    )
    .permute(2, 0, 1)
    .unsqueeze(0)
    .to(DEVICE)
)


# ==========================================================
# RUN U-NET
# ==========================================================

print()
print("Running glacier segmentation...")
print()

with torch.no_grad():

    output = model(tensor)

    probability = torch.sigmoid(
        output
    )

    probability = (
        probability
        .squeeze()
        .cpu()
        .numpy()
    )


# ==========================================================
# CREATE MASK
# ==========================================================

mask = (
    probability >= THRESHOLD
).astype(np.uint8)


# ==========================================================
# CALCULATE RESULTS
# ==========================================================

glacier_pixels = int(
    mask.sum()
)

total_pixels = int(
    mask.size
)

glacier_percentage = (
    glacier_pixels
    / total_pixels
) * 100


# ==========================================================
# SAVE MASK
# ==========================================================

mask_path = (
    OUTPUT_DIR
    / "gangotri_live_mask.png"
)

cv2.imwrite(
    str(mask_path),
    mask * 255
)


# ==========================================================
# CREATE OVERLAY
# ==========================================================

overlay = resized.copy()

overlay[mask == 1] = [
    255,
    0,
    0
]

overlay = cv2.addWeighted(
    resized,
    0.65,
    overlay,
    0.35,
    0
)

overlay_path = (
    OUTPUT_DIR
    / "gangotri_live_overlay.png"
)

cv2.imwrite(
    str(overlay_path),
    cv2.cvtColor(
        overlay,
        cv2.COLOR_RGB2BGR
    )
)


# ==========================================================
# RESULTS
# ==========================================================

print("==========================================")
print(" LIVE GLACIER ANALYSIS RESULTS")
print("==========================================")
print()

print("Model             : U-Net V2")
print("Input             : gangotri_latest.png")
print(
    "Input size        :",
    INPUT_SIZE,
    "x",
    INPUT_SIZE
)

print(
    "Glacier pixels    :",
    glacier_pixels
)

print(
    "Total pixels      :",
    total_pixels
)

print(
    "Glacier coverage  :",
    round(glacier_percentage, 2),
    "%"
)

print()

print("Mask saved to:")
print(mask_path)

print()

print("Overlay saved to:")
print(overlay_path)

print()
print("Live satellite AI analysis completed!")
print()