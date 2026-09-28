from pathlib import Path
import zipfile

# Path to the folder containing the ZIP files
rgi_folder = Path("datasets/raw/RGI")

# Extract all ZIP files
for zip_file in rgi_folder.glob("*.zip"):
    print(f"Extracting {zip_file.name}...")
    with zipfile.ZipFile(zip_file, "r") as z:
        z.extractall(rgi_folder)

print("\n✅ All RGI ZIP files extracted successfully!")