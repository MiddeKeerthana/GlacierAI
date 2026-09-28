from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import torch

from backend.models.unet import UNet


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]

CHECKPOINT_PATH = (
    PROJECT_DIR
    / "checkpoints"
    / "best_unet_v2.pth"
)

IMAGE_DIR = (
    PROJECT_DIR
    / "datasets"
    / "training"
    / "images"
)

OUTPUT_DIR = (
    PROJECT_DIR
    / "backend"
    / "outputs"
    / "predictions"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================================
# CONFIGURATION
# ==========================================================

INPUT_SIZE = 256
THRESHOLD = 0.5


# ==========================================================
# DEVICE
# ==========================================================

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("=" * 60)
print("GLACIERAI - U-NET V2 PREDICTION")
print("=" * 60)

print(f"Device: {DEVICE}")


# ==========================================================
# CHECK FILES
# ==========================================================

if not CHECKPOINT_PATH.exists():
    raise FileNotFoundError(
        f"\nV2 checkpoint not found:\n"
        f"{CHECKPOINT_PATH}"
    )

if not IMAGE_DIR.exists():
    raise FileNotFoundError(
        f"\nTraining image directory not found:\n"
        f"{IMAGE_DIR}"
    )


# ==========================================================
# LOAD MODEL
# ==========================================================

print("\nLoading V2 model...")

model = UNet().to(DEVICE)

checkpoint = torch.load(
    CHECKPOINT_PATH,
    map_location=DEVICE
)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()

print("Model loaded successfully!")

print(
    f"Checkpoint epoch : "
    f"{checkpoint['epoch']}"
)

print(
    f"Validation loss  : "
    f"{checkpoint['val_loss']:.4f}"
)

if "val_dice" in checkpoint:
    print(
        f"Validation Dice  : "
        f"{checkpoint['val_dice']:.4f}"
    )

if "val_iou" in checkpoint:
    print(
        f"Validation IoU   : "
        f"{checkpoint['val_iou']:.4f}"
    )


# ==========================================================
# FIND IMAGE
# ==========================================================

image_files = sorted(
    IMAGE_DIR.glob("*.png")
)

if not image_files:
    raise FileNotFoundError(
        f"No PNG images found in:\n{IMAGE_DIR}"
    )

# Use first training patch for the local test
image_file = image_files[0]

print(
    f"\nInput image: {image_file.name}"
)


# ==========================================================
# READ IMAGE
# ==========================================================

image = cv2.imread(
    str(image_file)
)

if image is None:
    raise ValueError(
        f"Could not read image:\n{image_file}"
    )

image = cv2.cvtColor(
    image,
    cv2.COLOR_BGR2RGB
)

print(
    f"Original image size: "
    f"{image.shape[1]} x {image.shape[0]}"
)


# ==========================================================
# PREPROCESS
# ==========================================================

# Dataset patches are 256 x 256.
image_256 = cv2.resize(
    image,
    (INPUT_SIZE, INPUT_SIZE),
    interpolation=cv2.INTER_LINEAR
)

# Convert to float and normalize to [0, 1]
image_normalized = (
    image_256.astype("float32") / 255.0
)


# ==========================================================
# CONVERT TO PYTORCH TENSOR
# ==========================================================

tensor = torch.from_numpy(
    image_normalized
).permute(
    2, 0, 1
).unsqueeze(
    0
).to(DEVICE)


# ==========================================================
# MODEL PREDICTION
# ==========================================================

print("\nRunning glacier segmentation...")

with torch.no_grad():

    output = model(tensor)

    probability = torch.sigmoid(output)

    probability = (
        probability
        .squeeze()
        .cpu()
        .numpy()
    )


# ==========================================================
# CREATE BINARY MASK
# ==========================================================

mask = (
    probability >= THRESHOLD
).astype("uint8")


# ==========================================================
# CALCULATE GLACIER COVERAGE
# ==========================================================

glacier_pixels = int(
    mask.sum()
)

total_pixels = int(
    mask.size
)

glacier_percentage = (
    glacier_pixels / total_pixels
) * 100


# ==========================================================
# SAVE MASK
# ==========================================================

mask_path = (
    OUTPUT_DIR
    / "predicted_mask.png"
)

cv2.imwrite(
    str(mask_path),
    mask * 255
)


# ==========================================================
# CREATE OVERLAY
# ==========================================================

overlay = image_256.copy()

# Make glacier pixels visible on the original image
overlay[mask == 1] = [0, 255, 255]

overlay_path = (
    OUTPUT_DIR
    / "glacier_overlay.png"
)

cv2.imwrite(
    str(overlay_path),
    cv2.cvtColor(
        overlay,
        cv2.COLOR_RGB2BGR
    )
)


# ==========================================================
# PRINT RESULTS
# ==========================================================

print()
print("=" * 60)
print("GLACIER PREDICTION RESULTS")
print("=" * 60)

print(
    f"Model             : U-Net V2"
)

print(
    f"Input              : {image_file.name}"
)

print(
    f"Input size         : "
    f"{INPUT_SIZE} x {INPUT_SIZE}"
)

print(
    f"Glacier pixels     : "
    f"{glacier_pixels}"
)

print(
    f"Total pixels       : "
    f"{total_pixels}"
)

print(
    f"Glacier coverage   : "
    f"{glacier_percentage:.2f}%"
)

print()
print(
    f"Mask saved to      : {mask_path}"
)

print(
    f"Overlay saved to   : {overlay_path}"
)

print("=" * 60)


# ==========================================================
# VISUALIZATION
# ==========================================================

plt.figure(
    figsize=(15, 5)
)

plt.subplot(1, 3, 1)

plt.imshow(image_256)

plt.title(
    "Satellite Image"
)

plt.axis("off")


plt.subplot(1, 3, 2)

plt.imshow(
    mask,
    cmap="gray"
)

plt.title(
    "Predicted Glacier Mask"
)

plt.axis("off")


plt.subplot(1, 3, 3)

plt.imshow(
    overlay
)

plt.title(
    "Glacier Segmentation Overlay"
)

plt.axis("off")


plt.tight_layout()

plt.show()