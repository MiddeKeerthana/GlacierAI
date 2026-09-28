from pathlib import Path
import random
import shutil

# ==========================================================
# Configuration
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

IMAGE_DIR = PROJECT_ROOT / "datasets" / "training" / "images"
MASK_DIR = PROJECT_ROOT / "datasets" / "training" / "masks"

OUTPUT = PROJECT_ROOT / "datasets" / "training"

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

random.seed(42)

# ==========================================================
# Create folders
# ==========================================================

for split in ["train", "val", "test"]:
    (OUTPUT / split / "images").mkdir(parents=True, exist_ok=True)
    (OUTPUT / split / "masks").mkdir(parents=True, exist_ok=True)

# ==========================================================
# Collect patches
# ==========================================================

image_files = sorted(IMAGE_DIR.glob("*.png"))

print(f"Found {len(image_files)} image patches")

random.shuffle(image_files)

total = len(image_files)

train_end = int(total * TRAIN_RATIO)
val_end = train_end + int(total * VAL_RATIO)

train_files = image_files[:train_end]
val_files = image_files[train_end:val_end]
test_files = image_files[val_end:]

# ==========================================================
# Copy function
# ==========================================================

def copy_split(files, split):

    for img in files:

        mask = MASK_DIR / img.name

        shutil.copy2(
            img,
            OUTPUT / split / "images" / img.name
        )

        shutil.copy2(
            mask,
            OUTPUT / split / "masks" / img.name
        )

# ==========================================================
# Copy datasets
# ==========================================================

copy_split(train_files, "train")
copy_split(val_files, "val")
copy_split(test_files, "test")

print("\n==========================")
print("Dataset Split Complete")
print("==========================")
print("Train :", len(train_files))
print("Val   :", len(val_files))
print("Test  :", len(test_files))