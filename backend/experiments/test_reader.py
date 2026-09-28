from app.services.sentinel_reader import get_band_metadata
from pathlib import Path

# Path to your SAFE folder
safe_folder = Path(__file__).resolve().parent.parent / "datasets" / "raw" / "Sentinel2"

# Find the first .SAFE folder automatically
safe_dirs = list(safe_folder.rglob("*.SAFE"))

if not safe_dirs:
    raise FileNotFoundError("No .SAFE folder found!")

print(f"Using SAFE folder:\n{safe_dirs[0]}\n")

image = get_band_metadata(str(safe_dirs[0]))

print("\nImage Shape:", image.shape)