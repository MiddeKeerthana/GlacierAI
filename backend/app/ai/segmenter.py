from pathlib import Path

import cv2
import numpy as np
import torch

from backend.models.unet import UNet


# ==========================================================
# PATHS
# ==========================================================

PROJECT_DIR = Path(__file__).resolve().parents[3]

MODEL_PATH = (
    PROJECT_DIR
    / "checkpoints"
    / "best_unet_v2.pth"
)


# ==========================================================
# MODEL CONFIGURATION
# ==========================================================

INPUT_SIZE = 256
THRESHOLD = 0.5


# ==========================================================
# DEVICE
# ==========================================================

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ==========================================================
# LOAD MODEL ONCE
# ==========================================================

model = UNet().to(DEVICE)

checkpoint = torch.load(
    MODEL_PATH,
    map_location=DEVICE
)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()


# ==========================================================
# SEGMENT IMAGE
# ==========================================================

def segment_image(image_path: str):
    """
    Run U-Net V2 glacier segmentation
    on a satellite image.
    """

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    # BGR → RGB
    image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )

    # Resize to model input size
    resized = cv2.resize(
        image,
        (INPUT_SIZE, INPUT_SIZE),
        interpolation=cv2.INTER_LINEAR
    )

    # Normalize exactly as training input
    normalized = (
        resized.astype(np.float32) / 255.0
    )

    # HWC → CHW → batch
    tensor = (
        torch.from_numpy(normalized)
        .permute(2, 0, 1)
        .unsqueeze(0)
        .to(DEVICE)
    )

    # ------------------------------------------------------
    # Prediction
    # ------------------------------------------------------

    with torch.no_grad():

        output = model(tensor)

        probability = torch.sigmoid(output)

        probability = (
            probability
            .squeeze()
            .cpu()
            .numpy()
        )

    # ------------------------------------------------------
    # Binary mask
    # ------------------------------------------------------

    mask = (
        probability >= THRESHOLD
    ).astype(np.uint8)

    # ------------------------------------------------------
    # Statistics
    # ------------------------------------------------------

    glacier_pixels = int(
        mask.sum()
    )

    total_pixels = int(
        mask.size
    )

    glacier_percentage = (
        glacier_pixels / total_pixels
    ) * 100

    return {
        "mask": mask,
        "probability": probability,
        "glacier_pixels": glacier_pixels,
        "total_pixels": total_pixels,
        "glacier_percentage": glacier_percentage,
    }