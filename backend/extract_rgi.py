from pathlib import Path
import zipfile

# Project root (GlacierAI)
project_root = Path(__file__).resolve().parent.parent

# Folder containing the ZIP files
rgi_folder = project_root / "datasets" / "raw" / "RGI"

print(f"RGI folder: {rgi_folder}")

for zip_file in rgi_folder.glob("*.zip"):
    print(f"Extracting {zip_file.name}...")
    with zipfile.ZipFile(zip_file, "r") as z:
        z.extractall(rgi_folder)

print("\n✅ All RGI ZIP files extracted successfully!")