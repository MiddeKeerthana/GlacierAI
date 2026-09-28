from pathlib import Path
from zipfile import ZipFile
import shutil

# =====================================================
# Paths
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RGI_ZIP_FOLDER = PROJECT_ROOT / "datasets" / "raw" / "RGI"

OUTPUT_FOLDER = PROJECT_ROOT / "datasets" / "processed" / "RGI"

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# =====================================================
# Extract all ZIP files
# =====================================================

zip_files = sorted(RGI_ZIP_FOLDER.glob("*.zip"))

if len(zip_files) == 0:
    print("No ZIP files found!")
    exit()

print("=" * 60)
print(f"Found {len(zip_files)} RGI ZIP files")
print("=" * 60)

for zip_path in zip_files:

    region_name = zip_path.stem

    destination = OUTPUT_FOLDER / region_name

    if destination.exists():
        print(f"Skipping {region_name} (already extracted)")
        continue

    destination.mkdir(parents=True)

    print(f"Extracting {region_name}")

    with ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(destination)

print("\nExtraction Completed Successfully!")

print("=" * 60)
print("Output Folder:")
print(OUTPUT_FOLDER)
print("=" * 60)