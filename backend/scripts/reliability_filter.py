import json
from pathlib import Path


HIGH_DICE = 0.70
HIGH_IOU = 0.50

MEDIUM_DICE = 0.50
MEDIUM_IOU = 0.35


def classify_reliability(dice, iou):
    """
    Classify an observation using RGI-overlap validation metrics.
    """

    if dice >= HIGH_DICE and iou >= HIGH_IOU:
        return "HIGH"

    if dice >= MEDIUM_DICE and iou >= MEDIUM_IOU:
        return "MEDIUM"

    return "LOW"


def process_historical_results(glacier_name):
    slug = glacier_name.lower().replace(" ", "_")

    project_root = Path(__file__).resolve().parents[2]

    results_path = (
        project_root
        / "datasets"
        / "historical"
        / slug
        / "historical_results.json"
    )

    if not results_path.exists():
        raise FileNotFoundError(
            f"Historical results not found:\n{results_path}"
        )

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print()
    print("=" * 70)
    print(" GLACIERAI - HISTORICAL RELIABILITY ANALYSIS")
    print("=" * 70)

    print(f"Glacier: {glacier_name}")
    print()

    observations = data.get("observations", [])

    if not observations:
        print("No historical observations found.")
        return

    reliable_observations = []
    high_confidence_observations = []

    for observation in observations:

        year = observation.get("year")

        validation = observation.get("validation", {})

        dice = validation.get("rgi_overlap_dice")
        iou = validation.get("rgi_overlap_iou")

        if dice is None or iou is None:
            print(
                f"{year} | "
                "Validation metrics unavailable"
            )
            continue

        reliability = classify_reliability(dice, iou)

        observation["reliability"] = reliability

        if reliability in ("HIGH", "MEDIUM"):
            reliable_observations.append(observation)

        if reliability == "HIGH":
            high_confidence_observations.append(observation)

        print(
            f"{year} | "
            f"Dice: {dice:.4f} | "
            f"IoU: {iou:.4f} | "
            f"Reliability: {reliability}"
        )

    # Store reliability information
    data["reliability"] = {
        "method": "RGI-overlap based reliability classification",

        "thresholds": {
            "high": {
                "dice_min": HIGH_DICE,
                "iou_min": HIGH_IOU
            },
            "medium": {
                "dice_min": MEDIUM_DICE,
                "iou_min": MEDIUM_IOU
            }
        },

        "reliable_years": [
            observation.get("year")
            for observation in reliable_observations
        ],

        "high_confidence_years": [
            observation.get("year")
            for observation in high_confidence_observations
        ],

        "low_confidence_years": [
            observation.get("year")
            for observation in observations
            if observation.get("reliability") == "LOW"
        ]
    }

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print()
    print("=" * 70)
    print(" RELIABILITY ANALYSIS COMPLETE")
    print("=" * 70)

    print(
        "Reliable observations:",
        len(reliable_observations)
    )

    print(
        "Reliable years:",
        data["reliability"]["reliable_years"]
    )

    print(
        "High-confidence years:",
        data["reliability"]["high_confidence_years"]
    )

    print(
        "Low-confidence years:",
        data["reliability"]["low_confidence_years"]
    )

    print()
    print("Updated:")
    print(results_path)


if __name__ == "__main__":
    process_historical_results("Mana Glacier")