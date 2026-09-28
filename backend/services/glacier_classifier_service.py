from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from torchvision.models import swin_t


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "checkpoints"
    / "glacier_classifier_swin_v1.pth"
)


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# CLASSES
# ============================================================

CLASS_NAMES = [
    "glacieret_snowfield",
    "ice_cap",
    "mountain_glacier",
]

DISPLAY_NAMES = {
    "glacieret_snowfield": "Glacieret / Snowfield",
    "ice_cap": "Ice Cap",
    "mountain_glacier": "Mountain Glacier",
}


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[
            0.485,
            0.456,
            0.406,
        ],
        std=[
            0.229,
            0.224,
            0.225,
        ],
    ),
])


# ============================================================
# MODEL
# ============================================================

def build_model():
    """
    Build the same Swin-T architecture used during training.
    """

    model = swin_t(weights=None)

    in_features = model.head.in_features

    model.head = nn.Sequential(
        nn.Dropout(0.35),
        nn.Linear(
            in_features,
            len(CLASS_NAMES),
        ),
    )

    return model


# ============================================================
# LOAD MODEL
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Swin classifier checkpoint not found:\n{MODEL_PATH}"
    )

_checkpoint = torch.load(
    MODEL_PATH,
    map_location=DEVICE,
)

model = build_model()

# The training checkpoint contains model_state_dict.
if "model_state_dict" in _checkpoint:
    model.load_state_dict(
        _checkpoint["model_state_dict"]
    )
else:
    # Fallback in case a raw state_dict is provided.
    model.load_state_dict(_checkpoint)

model = model.to(DEVICE)

model.eval()


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_glacier(image_path):
    """
    Classify a glacier image using the trained Swin Transformer.

    Returns:
        dict containing:
        - class
        - display_name
        - confidence
        - confidence_percent
        - probabilities
        - source
    """

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found:\n{image_path}"
        )

    # --------------------------------------------------------
    # Load image
    # --------------------------------------------------------

    image = Image.open(image_path).convert("RGB")

    tensor = TRANSFORM(image)

    tensor = tensor.unsqueeze(0)

    tensor = tensor.to(DEVICE)

    # --------------------------------------------------------
    # Inference
    # --------------------------------------------------------

    with torch.no_grad():

        outputs = model(tensor)

        probabilities = torch.softmax(
            outputs,
            dim=1,
        )[0]

    predicted_index = int(
        torch.argmax(probabilities).item()
    )

    predicted_class = CLASS_NAMES[
        predicted_index
    ]

    confidence = float(
        probabilities[predicted_index].item()
    )

    # --------------------------------------------------------
    # Probability dictionary
    # --------------------------------------------------------

    probability_dict = {}

    for index, class_name in enumerate(CLASS_NAMES):

        probability_dict[class_name] = round(
            float(probabilities[index].item()),
            4,
        )

    # --------------------------------------------------------
    # Confidence level
    # --------------------------------------------------------

    if confidence >= 0.80:
        confidence_level = "High"

    elif confidence >= 0.60:
        confidence_level = "Moderate"

    else:
        confidence_level = "Low"

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {
        "class": predicted_class,

        "display_name": DISPLAY_NAMES[
            predicted_class
        ],

        "confidence": round(
            confidence,
            4,
        ),

        "confidence_percent": round(
            confidence * 100,
            2,
        ),

        "confidence_level": confidence_level,

        "probabilities": probability_dict,

        "source": "Swin Transformer",
    }